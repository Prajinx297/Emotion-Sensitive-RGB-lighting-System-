import cv2
from fer.fer import FER
from ultralytics import YOLO
import serial
import time
import csv
import os
from collections import deque
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
SERIAL_PORT           = 'COM5'
BAUD_RATE             = 9600
FRAME_SKIP_INTERVAL   = 3          # Process every Nth frame (CPU saver)
HIGH_STRESS_THRESHOLD = 65         # 0-100; triggers wellness alert
ALERT_COOLDOWN_SEC    = 45         # Min seconds between consecutive alerts
EMOTION_HISTORY_LEN   = 5          # Rolling window size for stable emotion
YOLO_CONF             = 0.55       # YOLO detection confidence threshold
PATIENT_MODE_DEFAULT  = False      # Start in normal mode

# ── Patient-mode movement detection ──────────────────────────────────────────
MOVEMENT_THRESHOLD    = 25         # Mean pixel diff to count as "moving"
MOVEMENT_BUZZ_MIN_SEC = 2.0        # Buzzer rings for AT LEAST this many seconds

# ─────────────────────────────────────────────
#  SERIAL / ARDUINO SETUP
# ─────────────────────────────────────────────
def init_arduino(port: str, baud: int):
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)
        print(f"✅ Arduino connected on {port}")
        return ser
    except Exception as e:
        print(f"⚠️  Arduino not found ({e}) — running in display-only mode")
        return None

# ─────────────────────────────────────────────
#  SESSION LOGGING
# ─────────────────────────────────────────────
def init_log() -> str:
    path = f"session_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(path, 'w', newline='') as f:
        csv.writer(f).writerow(["Timestamp", "Emotion", "Activity", "StressScore", "Mode"])
    print(f"📄 Logging → {path}")
    return path

def append_log(path: str, emotion: str, activity: str, stress: int, mode: str):
    with open(path, 'a', newline='') as f:
        csv.writer(f).writerow([datetime.now().strftime('%H:%M:%S'), emotion, activity, stress, mode])

# ─────────────────────────────────────────────
#  EMOTION HELPERS
# ─────────────────────────────────────────────
def dominant_emotion(history: deque) -> str:
    """Return most frequent emotion in the rolling window."""
    return max(set(history), key=history.count) if history else "neutral"

def compute_stress(e: dict) -> int:
    """Map FER emotion probabilities to a 0–100 stress score."""
    if not e:
        return 0
    stressed = e.get('angry', 0)*0.40 + e.get('fear', 0)*0.35 + e.get('disgust', 0)*0.25
    calm     = e.get('happy',  0)*0.50 + e.get('surprise', 0)*0.20 + e.get('neutral', 0)*0.30
    return max(0, min(100, int((stressed - calm*0.5 + 1) / 2 * 100)))

# ─────────────────────────────────────────────
#  ACTIVITY CLASSIFIER
# ─────────────────────────────────────────────
_ACTIVITY_MAP = {
    'joystick':  'gaming',   'cell phone': 'gaming',
    'laptop':    'working',  'keyboard':   'working',  'mouse': 'working',
    'book':      'studying', 'notebook':   'studying', 'pen':   'studying',
    'remote':    'relaxing', 'tv':         'relaxing',
}

def classify_activity(objects: list) -> str:
    for obj in (o.lower() for o in objects):
        if obj in _ACTIVITY_MAP:
            return _ACTIVITY_MAP[obj]
    return 'idle'

# ─────────────────────────────────────────────
#  ENCODING TABLES  (kept identical to original)
# ─────────────────────────────────────────────
EMOTION_CODES = {
    'happy':'000', 'sad':'001', 'angry':'010', 'neutral':'011',
    'fear':'100', 'surprised':'101', 'disgusted':'110',
}
ACTIVITY_CODES = {
    'gaming':'00', 'working':'01', 'studying':'10',
    'idle':'11',   'relaxing':'11',
}

# ─────────────────────────────────────────────
#  SERIAL SENDER
# ─────────────────────────────────────────────
_last_alert_time  = 0
_last_sent_packet = None          # Avoid redundant serial writes

def send_to_arduino(arduino, emotion: str, activity: str, stress: int,
                    patient_mode: bool, log_path: str, mode_label: str,
                    patient_moving: bool = False):
    """
    Build and transmit the encoded packet.
    In patient mode `patient_moving` overrides the activity code:
      '10' = moving / DANGER
      '00' = stable
    The rest of the packet (emotion bits + stress digit) is preserved.
    """
    global _last_alert_time, _last_sent_packet

    e_code = EMOTION_CODES.get(emotion, '011')

    if patient_mode:
        # Activity field repurposed as patient movement level
        a_code = '10' if patient_moving else '00'
    else:
        # ── Normal mode: derive from activity / stress ─────────────────
        a_code = ACTIVITY_CODES.get(activity, '11')
        if stress >= HIGH_STRESS_THRESHOLD or activity not in ('idle', 'relaxing'):
            pass   # keep a_code as-is; original logic unchanged

    s_digit = min(9, stress // 10)
    packet  = f"{e_code},{a_code},{s_digit}"

    # ── Deduplicate: only send when state changes ──────────────────────
    if packet == _last_sent_packet:
        return
    _last_sent_packet = packet

    if arduino:
        arduino.write((packet + '\n').encode())

    status_icon = '🏥' if patient_mode else '😶'
    label       = 'PatientStatus' if patient_mode else 'Activity'
    activity_display = ('MOVING' if patient_moving else 'STABLE') if patient_mode else activity
    print(f"{status_icon} Emotion:{emotion:10s} {e_code} | "
          f"{label}:{activity_display:8s} {a_code} | "
          f"Stress:{stress:3d}/100 → {packet}")

    # ── Wellness / danger alert (normal mode only; patient buzzer handled separately) ──
    if not patient_mode:
        now = time.time()
        if stress >= HIGH_STRESS_THRESHOLD and (now - _last_alert_time) > ALERT_COOLDOWN_SEC:
            if arduino:
                arduino.write(b"ALERT\n")
            _last_alert_time = now
            print("🚨 Alert sent!")

    append_log(log_path, emotion, activity_display, stress, mode_label)

# ─────────────────────────────────────────────
#  MOVEMENT DETECTOR  (patient mode only)
# ─────────────────────────────────────────────
class MovementDetector:
    """
    Frame-difference based movement detector.
    Keeps track of buzzer timing to enforce the minimum ring duration.
    """
    def __init__(self, threshold: float = MOVEMENT_THRESHOLD,
                 min_buzz_sec: float = MOVEMENT_BUZZ_MIN_SEC):
        self.threshold     = threshold
        self.min_buzz_sec  = min_buzz_sec
        self.prev_gray     = None
        self._moving       = False
        self._buzz_end     = 0.0      # wall-clock time when minimum buzz period ends

    def update(self, frame) -> bool:
        """
        Call with the current (possibly colour) frame.
        Returns True when the patient is moving (or the minimum buzz period
        has not yet elapsed since movement started).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self.prev_gray is None:
            self.prev_gray = gray
            return False

        diff   = cv2.absdiff(self.prev_gray, gray)
        mean_d = float(diff.mean())
        self.prev_gray = gray

        now       = time.time()
        moving_now = mean_d > self.threshold

        if moving_now:
            self._moving  = True
            # Extend (or start) the minimum-buzz window
            self._buzz_end = now + self.min_buzz_sec
        else:
            # Still hold "moving" state until minimum buzz window expires
            self._moving = now < self._buzz_end

        return self._moving

    def reset(self):
        """Call when switching modes so stale frames don't trigger movement."""
        self.prev_gray = None
        self._moving   = False
        self._buzz_end = 0.0

# ─────────────────────────────────────────────
#  OVERLAY DRAWING
# ─────────────────────────────────────────────
def draw_overlay_normal(frame, emotion: str, activity: str, stress: int, results=None):
    """
    Normal-mode overlay: emotion, activity, stress bar, YOLO bounding boxes.
    `results` must be the raw list returned by model.predict() so that
    results[0].plot() can render bounding boxes correctly.
    """
    # Use YOLO's built-in renderer when results are available
    out = results[0].plot() if (results is not None) else frame.copy()

    # Stress bar
    bar_w = int(stress / 100 * 200)
    bar_c = (0, int(255 - stress * 2.55), int(stress * 2.55))
    cv2.rectangle(out, (20, 130), (220, 150), (50, 50, 50), -1)
    cv2.rectangle(out, (20, 130), (20 + bar_w, 150), bar_c, -1)
    cv2.putText(out, f'Stress: {stress}%', (20, 125),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, bar_c, 2)

    cv2.putText(out, f'Emotion: {emotion}',   (20,  50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 2)
    cv2.putText(out, f'Activity: {activity}', (20,  95),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 200, 255), 2)

    return out


def draw_overlay_patient(frame, moving: bool):
    """
    Patient-mode overlay: clean UI — only stable/moving status, no stress bar,
    no emotion text, no activity text, no YOLO boxes.
    """
    out = frame.copy()

    if moving:
        label = "PATIENT MOVING!"
        color = (0, 0, 255)   # Red
    else:
        label = "PATIENT STABLE"
        color = (0, 255, 0)   # Green

    # Large centred status text
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 1.4, 3)
    h, w = out.shape[:2]
    x = (w - tw) // 2
    y = (h + th) // 2

    # Semi-transparent background pill for readability
    padding = 14
    overlay = out.copy()
    cv2.rectangle(overlay,
                  (x - padding, y - th - padding),
                  (x + tw + padding, y + padding),
                  (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, out, 0.55, 0, out)

    cv2.putText(out, label, (x, y),
                cv2.FONT_HERSHEY_DUPLEX, 1.4, color, 3, cv2.LINE_AA)

    # Small mode badge in top-left
    cv2.putText(out, 'PATIENT MODE', (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 100, 255), 2)

    return out

# ─────────────────────────────────────────────
#  MAIN DETECTION LOOP
# ─────────────────────────────────────────────
def run():
    arduino      = init_arduino(SERIAL_PORT, BAUD_RATE)
    log_path     = init_log()
    emotion_hist = deque(maxlen=EMOTION_HISTORY_LEN)
    patient_mode = PATIENT_MODE_DEFAULT
    move_det     = MovementDetector()

    print("⏳ Loading models…")
    emotion_detector = FER(mtcnn=True)
    activity_model   = YOLO('yolov8m.pt')
    print("✅ Models ready\n")

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("❌ Cannot open webcam")
        return

    print("🎥 Running — press 'q' quit | 'p' toggle patient mode\n")

    frame_idx    = 0
    emotion      = "neutral"
    activity     = "idle"
    stress       = 0
    patient_moving = False
    yolo_results   = None          # Holds last YOLO result list for normal mode

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)

        # ── Process every Nth frame (saves CPU) ───────────────────────
        if frame_idx % FRAME_SKIP_INTERVAL == 0:

            if patient_mode:
                # ── PATIENT MODE: movement detection only ─────────────
                patient_moving = move_det.update(frame)
                mode_label     = "patient"

                # Send buzzer state via Arduino serial flag
                if patient_moving:
                    send_to_arduino(arduino, emotion, activity, stress,
                                    True, log_path, mode_label,
                                    patient_moving=True)
                else:
                    send_to_arduino(arduino, emotion, activity, stress,
                                    True, log_path, mode_label,
                                    patient_moving=False)

            else:
                # ── NORMAL MODE: full emotion + activity pipeline ──────
                detections = emotion_detector.detect_emotions(frame)
                if detections:
                    raw = detections[0]['emotions']
                    emotion_hist.append(max(raw, key=raw.get))
                    emotion = dominant_emotion(emotion_hist)
                    stress  = compute_stress(raw)

                yolo_results = activity_model.predict(
                    source=frame, conf=YOLO_CONF, verbose=False)
                names    = activity_model.names
                objects  = [names[int(c)] for r in yolo_results for c in r.boxes.cls]
                activity = classify_activity(objects)

                mode_label = "normal"
                send_to_arduino(arduino, emotion, activity, stress,
                                False, log_path, mode_label,
                                patient_moving=False)

        frame_idx += 1

        # ── Draw overlay ───────────────────────────────────────────────
        if patient_mode:
            out = draw_overlay_patient(frame, patient_moving)
        else:
            out = draw_overlay_normal(frame, emotion, activity, stress,
                                      results=yolo_results)

        cv2.imshow("Emotion + Activity Monitor", out)

        # ── Key handling ───────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("\n🛑 Stopping…")
            break

        elif key == ord('p'):
            patient_mode = not patient_mode
            move_det.reset()              # Flush stale frames on mode switch
            yolo_results = None           # Clear YOLO boxes when entering patient mode

            if patient_mode:
                if arduino:
                    arduino.write(b"PATIENT_ON\n")
                print("🔄 Patient mode ON")
            else:
                if arduino:
                    arduino.write(b"PATIENT_OFF\n")
                print("🔄 Patient mode OFF")

    cap.release()
    cv2.destroyAllWindows()
    if arduino:
        arduino.close()
        print("🔌 Arduino disconnected")
    print(f"📄 Session saved → {log_path}")


if __name__ == "__main__":
    run()
