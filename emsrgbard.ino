#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ─── PINS ────────────────────────────────────────────
#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT  64
#define OLED_DC         8
#define OLED_CS        10
#define OLED_RESET      9

const int PIN_RED   = 5;
const int PIN_GREEN = 6;
const int PIN_BLUE  = 7;
const int PIN_BUZZ  = 4;

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT,
                         &SPI, OLED_DC, OLED_RESET, OLED_CS);

// ─── STATE ───────────────────────────────────────────
String  currentEmotion  = "NEUTRAL";
String  currentActivity = "IDLE";
int     stressLevel     = 0;
bool    alertActive     = false;
bool    patientMode     = false;
String  currentTimeStr  = "--:--";

unsigned long alertStart        = 0;
unsigned long activityStartTime = 0;
unsigned long lastDisplayUpdate = 0;

// ─── BREATHING ───────────────────────────────────────
bool          breathingActive = false;
float         breathVal       = 0;
bool          breathUp        = true;
unsigned long lastBreathStep  = 0;

// ─── BUZZER ─────────────────────────────────────────
bool          buzzerActive     = false;

// ─── TARGET COLOR ───────────────────────────────────
int tR = 0, tG = 255, tB = 0;
bool manualColorOverride = false;

// ───────────────── DECODERS ─────────────────────────
// DECODERS REMOVED: Python now sends plain text (e.g., "HAPPY")

// ───────────────── RGB ──────────────────────────────
void setColor(int r, int g, int b) {
  analogWrite(PIN_RED,   255 - r);
  analogWrite(PIN_GREEN, 255 - g);
  analogWrite(PIN_BLUE,  255 - b);
}

void getTargetColorNormal() {
  if (currentActivity == "GAMING")  { tR=255; tG=0;   tB=255; return; }
  if (currentActivity == "WORKING") { tR=0;   tG=255; tB=255; return; }
  if (currentActivity == "STUDY")   { tR=255; tG=165; tB=0;   return; }

  if (currentEmotion == "HAPPY")     { tR=255; tG=255; tB=0; }
  else if (currentEmotion == "SAD")  { tR=0;   tG=0;   tB=255; }
  else if (currentEmotion == "ANGRY"){ tR=255; tG=0;   tB=0; }
  else if (currentEmotion == "FEAR") { tR=128; tG=0;   tB=128; }
  else if (currentEmotion == "SURPRISED"){ tR=255; tG=128; tB=0; }
  else if (currentEmotion == "DISGUSTED"){ tR=128; tG=255; tB=0; }
  else                               { tR=0;   tG=255; tB=0; }
}

void updateTargetColor() {
  if (manualColorOverride) return;
  getTargetColorNormal();
}

// ───────────────── BREATHING ────────────────────────
void handleBreathing() {
  if (!breathingActive) { setColor(tR, tG, tB); return; }

  if (millis() - lastBreathStep < 20) return;
  lastBreathStep = millis();

  breathUp ? (breathVal += 3.0) : (breathVal -= 3.0);

  if (breathVal >= 255) { breathVal = 255; breathUp = false; }
  if (breathVal <= 20)  { breathVal = 20;  breathUp = true; }

  float s = breathVal / 255.0;
  setColor((int)(tR*s), (int)(tG*s), (int)(tB*s));
}

// ───────────────── BUZZER ───────────────────────────
void handleBuzzer() {
  if (buzzerActive) {
    digitalWrite(PIN_BUZZ, HIGH);
  } else {
    digitalWrite(PIN_BUZZ, LOW);
  }
}

// ───────────────── OLED ─────────────────────────────
String formatTime(unsigned long seconds) {
  unsigned long m = seconds / 60, s = seconds % 60;
  return (m < 10 ? "0" : "") + String(m) + ":" + (s < 10 ? "0" : "") + String(s);
}

void drawStressBar(int level) {
  int barLen = map(level, 0, 100, 0, 108);
  display.drawRect(10, 56, 108, 7, SSD1306_WHITE);
  display.fillRect(10, 56, barLen, 7, SSD1306_WHITE);
}

void updateDisplay() {
  display.clearDisplay();

  // ── Header
  display.fillRect(0, 0, SCREEN_WIDTH, 14, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK);
  display.setTextSize(1);
  if (patientMode) {
    display.setCursor(18, 2);
    display.print("PATIENT MONITOR");
  } else {
    display.setCursor(14, 2);
    display.print("ACTIVITY TRACKER");
  }

  display.setTextColor(SSD1306_WHITE);

  if (patientMode) {
    // ── Patient Mode UI
    display.setTextSize(2);
    if (currentActivity == "DANGER") {
      display.setCursor(20, 20);
      display.print("MOVING!");
    } else {
      display.setCursor(30, 20);
      display.print("STABLE");
    }
  } else {
    // ── Normal Mode UI
    display.setTextSize(1);
    display.setCursor(0, 16);
    display.print("Mood: ");
    display.print(currentEmotion);

    display.setCursor(0, 28);
    display.print("Task: ");
    display.print(currentActivity);
  }

  // ── Bottom Section (Time + Stress)
  display.drawLine(0, 44, SCREEN_WIDTH, 44, SSD1306_WHITE);
  display.setTextSize(2);
  int tw = currentTimeStr.length() * 12;
  display.setCursor((SCREEN_WIDTH - tw) / 2, 46);
  display.print(currentTimeStr);

  if (!patientMode) {
    drawStressBar(stressLevel);
  }

  display.display();
}

// ───────────────── SETUP ────────────────────────────
void setup() {
  Serial.begin(9600);

  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_BLUE, OUTPUT);
  pinMode(PIN_BUZZ, OUTPUT);

  digitalWrite(PIN_BUZZ, LOW);

  // 🔥 LED TEST
  setColor(255,0,0); delay(500);
  setColor(0,255,0); delay(500);
  setColor(0,0,255); delay(500);

  setColor(0,255,0); // default

  if (!display.begin(SSD1306_SWITCHCAPVCC)) {
    while (true);
  }

  display.clearDisplay();
  display.setTextSize(2);
  display.setCursor(20,25);
  display.print("READY");
  display.display();

  delay(1500);

  activityStartTime = millis();
  lastDisplayUpdate = millis();

  updateTargetColor();
  updateDisplay();
}

// ───────────────── LOOP ─────────────────────────────
void loop() {

  if (Serial.available()) {
    String code = Serial.readStringUntil('\n');
    code.trim();

    // ── RGB Override ──────────────────────────────────
    if (code.startsWith("RGB,")) {
      int idx1 = code.indexOf(',', 4);
      int idx2 = code.indexOf(',', idx1 + 1);
      if (idx1 != -1 && idx2 != -1) {
        tR = code.substring(4, idx1).toInt();
        tG = code.substring(idx1 + 1, idx2).toInt();
        tB = code.substring(idx2 + 1).toInt();
        manualColorOverride = true;
        // Turn off breathing to allow solid custom color
        breathingActive = false; 
        setColor(tR, tG, tB);
      }
      return;
    }

    if (code == "AUTO_COLOR") {
      manualColorOverride = false;
      updateTargetColor();
      return;
    }

    if (code == "PATIENT_ON") {
      patientMode = true;
      updateDisplay();
      return;
    }

    if (code == "PATIENT_OFF") {
      patientMode = false;
      buzzerActive = false;
      updateDisplay();
      return;
    }

    if (code == "ALERT") {
      alertActive = true;
      alertStart  = millis();
      breathingActive = true;
      buzzerActive = true;
      return;
    }

    if (code == "R") {
      activityStartTime = millis();
      return;
    }

    // ── KEY-VALUE PARSER
    if (code.startsWith("E:")) {
      int idxA = code.indexOf(",A:");
      int idxS = code.indexOf(",S:");
      int idxT = code.indexOf(",T:");
      
      if (idxA != -1 && idxS != -1) {
        currentEmotion = code.substring(2, idxA);
        currentActivity = code.substring(idxA + 3, idxS);
        
        if (idxT != -1) {
          stressLevel = code.substring(idxS + 3, idxT).toInt();
          currentTimeStr = code.substring(idxT + 3);
        } else {
          stressLevel = code.substring(idxS + 3).toInt();
        }

        // High stress or danger activates breathing & buzzer
        breathingActive = (stressLevel >= 70); 

        bool danger = patientMode && (currentActivity == "DANGER");
        buzzerActive = (stressLevel >= 70) || danger;

        updateTargetColor();
      }
      return;
    }
  }

  handleBreathing();
  handleBuzzer();

  if (millis() - lastDisplayUpdate >= 1000) {
    lastDisplayUpdate = millis();
    updateDisplay();
  }
}