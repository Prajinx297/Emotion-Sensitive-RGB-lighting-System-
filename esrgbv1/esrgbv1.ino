#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_MOSI  11
#define OLED_CLK   13
#define OLED_DC     8
#define OLED_CS    10
#define OLED_RESET  9

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &SPI, OLED_DC, OLED_RESET, OLED_CS);

// RGB LED pins (Common Anode)
int redPin   = 5;
int greenPin = 6;
int bluePin  = 7;

// State
String currentEmotion  = "NEUTRAL";
String currentActivity = "IDLE";
int    stressLevel     = 0;   // 0–9
bool   alertActive     = false;
unsigned long alertStart = 0;

// Timer
unsigned long activityStartTime = 0;
unsigned long lastDisplayUpdate = 0;

// Breathing effect
bool   breathingActive = false;
float  breathVal       = 0;
bool   breathUp        = true;
unsigned long lastBreathStep = 0;

// Target color
int tR = 0, tG = 255, tB = 0;

// -------- Decoders --------
String decodeEmotion(String bits) {
  if      (bits == "000") return "HAPPY";
  else if (bits == "001") return "SAD";
  else if (bits == "010") return "ANGRY";
  else if (bits == "011") return "NEUTRAL";
  else if (bits == "100") return "FEAR";
  else if (bits == "101") return "SURPRISED";
  else if (bits == "110") return "DISGUSTED";
  else                    return "NEUTRAL";
}

String decodeActivity(String bits) {
  if      (bits == "00") return "GAMING";
  else if (bits == "01") return "WORKING";
  else if (bits == "10") return "STUDY";
  else                   return "IDLE";
}

// -------- RGB --------
void setColor(int r, int g, int b) {
  analogWrite(redPin,   255 - r);
  analogWrite(greenPin, 255 - g);
  analogWrite(bluePin,  255 - b);
}

void getTargetColor(String emotion, String activity) {
  if (activity == "GAMING")   { tR=255; tG=0;   tB=255; return; } // Purple
  if (activity == "WORKING")  { tR=0;   tG=255; tB=255; return; } // Cyan
  if (activity == "STUDY")    { tR=255; tG=165; tB=0;   return; } // Orange

  // IDLE/RELAX → emotion
  if      (emotion == "HAPPY")     { tR=255; tG=255; tB=0;   }
  else if (emotion == "SAD")       { tR=0;   tG=0;   tB=255; }
  else if (emotion == "ANGRY")     { tR=255; tG=0;   tB=0;   }
  else if (emotion == "FEAR")      { tR=128; tG=0;   tB=128; }
  else if (emotion == "SURPRISED") { tR=255; tG=128; tB=0;   }
  else if (emotion == "DISGUSTED") { tR=128; tG=255; tB=0;   }
  else                             { tR=0;   tG=255; tB=0;   } // Green = Neutral
}

// -------- Breathing Effect --------
// Called every loop; smoothly pulses LED brightness when stress is high
void handleBreathing() {
  if (!breathingActive) {
    setColor(tR, tG, tB);
    return;
  }

  if (millis() - lastBreathStep < 20) return; // 20ms step = ~4s full cycle
  lastBreathStep = millis();

  if (breathUp) {
    breathVal += 3.0;
    if (breathVal >= 255) { breathVal = 255; breathUp = false; }
  } else {
    breathVal -= 3.0;
    if (breathVal <= 20)  { breathVal = 20;  breathUp = true;  }
  }

  float scale = breathVal / 255.0;
  setColor((int)(tR * scale), (int)(tG * scale), (int)(tB * scale));
}

// -------- Format MM:SS --------
String formatTime(unsigned long seconds) {
  unsigned long m = seconds / 60;
  unsigned long s = seconds % 60;
  return (m < 10 ? "0" : "") + String(m) + ":" + (s < 10 ? "0" : "") + String(s);
}

// -------- Stress Bar on OLED --------
void drawStressBar(int level) {
  // level 0–9 → maps to pixel width 0–108
  int barLen = map(level, 0, 9, 0, 108);
  display.drawRect(10, 56, 108, 7, SSD1306_WHITE);
  display.fillRect(10, 56, barLen, 7, SSD1306_WHITE);
}

// -------- OLED Display --------
void updateDisplay() {
  unsigned long elapsed = (millis() - activityStartTime) / 1000;
  String t = formatTime(elapsed);

  display.clearDisplay();

  // Title bar
  display.fillRect(0, 0, SCREEN_WIDTH, 12, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK);
  display.setTextSize(1);
  display.setCursor(18, 2);
  display.print("ACTIVITY TRACKER");

  // Alert overlay
  if (alertActive && (millis() - alertStart < 5000)) {
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(8, 16);
    display.print("!! TAKE A BREAK !!");
    display.setCursor(16, 28);
    display.print("Breathe slowly...");
    display.setCursor(22, 40);
    display.print("You got this :)");
    drawStressBar(stressLevel);
    display.display();
    return;
  } else if (alertActive) {
    alertActive = false;
  }

  // Mood
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 16);
  display.print("Mood: ");
  display.print(currentEmotion);

  // Task
  display.setCursor(0, 28);
  display.print("Task: ");
  display.print(currentActivity);

  // Divider
  display.drawLine(0, 38, SCREEN_WIDTH, 38, SSD1306_WHITE);

  // Timer
  display.setTextSize(2);
  int tw = t.length() * 12;
  display.setCursor((SCREEN_WIDTH - tw) / 2, 41);
  display.print(t);

  // Stress bar at bottom
  drawStressBar(stressLevel);

  display.display();
}

// -------- Setup --------
void setup() {
  Serial.begin(9600);
  pinMode(redPin,   OUTPUT);
  pinMode(greenPin, OUTPUT);
  pinMode(bluePin,  OUTPUT);
  setColor(0, 0, 0);

  if (!display.begin(SSD1306_SWITCHCAPVCC)) {
    Serial.println("OLED not found!");
    for (;;);
  }

  display.clearDisplay();
  display.setTextSize(2);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(20, 25);
  display.print("READY");
  display.display();
  delay(1500);

  activityStartTime = millis();
  lastDisplayUpdate  = millis();
  updateDisplay();
}

// -------- Loop --------
void loop() {

  if (Serial.available()) {
    String code = Serial.readStringUntil('\n');
    code.trim();

    // Wellness alert from Python
    if (code == "ALERT") {
      alertActive = true;
      alertStart  = millis();
      breathingActive = true;  // start breathing during alert
      updateDisplay();
      return;
    }

    // Reset timer
    if (code == "R") {
      activityStartTime = millis();
      return;
    }

    // Format: eee,aa,s   e.g. "010,01,7"
    int c1 = code.indexOf(',');
    int c2 = code.lastIndexOf(',');
    if (c1 != -1 && c2 != -1 && c1 != c2) {
      String eBits = code.substring(0, c1);
      String aBits = code.substring(c1 + 1, c2);
      String sBit  = code.substring(c2 + 1);

      currentEmotion  = decodeEmotion(eBits);
      currentActivity = decodeActivity(aBits);
      stressLevel     = sBit.toInt();

      // ✨ Breathing ON when stress >= 7, OFF otherwise
      breathingActive = (stressLevel >= 7);

      getTargetColor(currentEmotion, currentActivity);
    }
  }

  // Breathing / static LED update
  handleBreathing();

  // OLED update every second
  if (millis() - lastDisplayUpdate >= 1000) {
    lastDisplayUpdate = millis();
    updateDisplay();
  }
}