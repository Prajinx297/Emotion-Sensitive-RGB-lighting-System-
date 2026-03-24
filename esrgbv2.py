import cv2
from fer import FER
from ultralytics import YOLO
import serial
import time
import csv
import os
from collections import deque
from datetime import datetime

# ----------------- SETUP -----------------
try:
    arduino = serial.Serial('COM12', 9600, timeout=1)
    time.sleep(2)
    print("✅ Arduino connected via USB Serial.")
except Exception as e:
    print(f"⚠️ Arduino connection failed: {e}")
    arduino = None

print("⏳ Loading models...")
emotion_detector = FER(mtcnn=True)
activity_model = YOLO('yolov8m.pt')
print("✅ Models loaded.\n")

# ----------------- SESSION LOG SETUP -----------------
LOG_FILE = f"session_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
with open(LOG_FILE, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Timestamp", "Emotion", "Activity", "StressScore"])
print(f"📄 Logging to: {LOG_FILE}")

# ----------------- EMOTION HISTORY (Rolling Window) -----------------
EMOTION_HISTORY = deque(maxlen=5)

def get_dominant_emotion(history):
    if not history:
        return "neutral"
    return max(set(history), key=history.count)

# ----------------- STRESS SCORE -----------------
def compute_stress(emotions_dict):
    """Returns 0–100 stress score from raw FER emotion probabilities."""
    if not emotions_dict:
        return 0
    stress = (
        emotions_dict.get('angry', 0) * 0.40 +
        emotions_dict.get('fear',  0) * 0.35 +
        emotions_dict.get('disgust', 0) * 0.25
    )
    calm = (
        emotions_dict.get('happy',    0) * 0.50 +
        emotions_dict.get('surprise', 0) * 0.20 +
        emotions_dict.get('neutral',  0) * 0.30
    )
    score = int((stress - calm * 0.5 + 1) / 2 * 100)
    return max(0, min(100, score))

# ----------------- ACTIVITY CLASSIFIER -----------------
def classify_activity(objects):
    objects = [o.lower() for o in objects]
    if 'joystick' in objects or 'cell phone' in objects:
        return 'gaming'
    elif 'laptop' in objects or 'keyboard' in objects or 'mouse' in objects:
        return 'working'
    elif 'book' in objects or 'notebook' in objects or 'pen' in objects:
        return 'studying'
    elif 'remote' in objects or 'tv' in objects:
        return 'relaxing'
    else:
        return 'idle'

# ----------------- ENCODE & SEND -----------------
# Expanded emotion set: 3 bits now
EMOTION_CODES = {
    'happy':     '000',
    'sad':       '001',
    'angry':     '010',
    'neutral':   '011',
    'fear':      '100',
    'surprised': '101',
    'disgusted': '110',
}

ACTIVITY_CODES = {
    'gaming':   '00',
    'working':  '01',
    'studying': '10',
    'idle':     '11',
    'relaxing': '11',
}

last_stress_alert_time = 0
HIGH_STRESS_THRESHOLD  = 65
ALERT_COOLDOWN_SEC     = 45

def send_to_arduino(emotion, activity, stress_score):
    global last_stress_alert_time

    if not arduino:
        return

    e_code = EMOTION_CODES.get(emotion, '011')
    a_code = ACTIVITY_CODES.get(activity, '11')

    # Pack stress into 0–9 single digit (maps 0–100 → 0–9)
    stress_digit = min(9, stress_score // 10)

    data = f"{e_code},{a_code},{stress_digit}\n"
    arduino.write(data.encode())

    print(f"😶 Emotion: {emotion:10s} {e_code} | 🎮 Activity: {activity:8s} {a_code} | 😰 Stress: {stress_score:3d}/100 | Sent: {data.strip()}")

    # Wellness alert logic
    now = time.time()
    if stress_score >= HIGH_STRESS_THRESHOLD and (now - last_stress_alert_time) > ALERT_COOLDOWN_SEC:
        arduino.write(b"ALERT\n")
        last_stress_alert_time = now
        print("🚨 Wellness alert sent to Arduino!")

    # Log to CSV
    with open(LOG_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().strftime('%H:%M:%S'), emotion, activity, stress_score])

# ----------------- MAIN -----------------
def run_combined_detection():
    cap = cv2.VideoCapture(0)
    cap.set(3, 640)
    cap.set(4, 480)

    if not cap.isOpened():
        print("❌ Cannot open webcam.")
        return

    print("🎥 Detection started. Press 'q' to quit.\n")

    frame_skip  = 0
    emotion     = "neutral"
    activity    = "idle"
    stress      = 0
    raw_emotions = {}
    results     = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)

        if frame_skip % 3 == 0:
            # --- Emotion ---
            emotion_results = emotion_detector.detect_emotions(frame)
            if emotion_results:
                raw_emotions = emotion_results[0]['emotions']
                instant_emotion = max(raw_emotions, key=raw_emotions.get)
                EMOTION_HISTORY.append(instant_emotion)
                emotion = get_dominant_emotion(EMOTION_HISTORY)  # ✨ Stable dominant emotion
                stress  = compute_stress(raw_emotions)            # ✨ Stress score

            # --- Activity ---
            results = activity_model.predict(source=frame, conf=0.55, verbose=False)
            names   = activity_model.names
            detected_objects = [names[int(c)] for r in results for c in r.boxes.cls]
            activity = classify_activity(detected_objects)

            send_to_arduino(emotion, activity, stress)

        frame_skip += 1

        # Draw
        if results:
            annotated_frame = results[0].plot()
        else:
            annotated_frame = frame.copy()

        # Stress bar
        bar_w = int((stress / 100) * 200)
        bar_color = (0, 255 - int(stress * 2.55), int(stress * 2.55))  # green→red
        cv2.rectangle(annotated_frame, (20, 130), (220, 150), (50, 50, 50), -1)
        cv2.rectangle(annotated_frame, (20, 130), (20 + bar_w, 150), bar_color, -1)
        cv2.putText(annotated_frame, f'Stress: {stress}%', (20, 125),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, bar_color, 2)

        cv2.putText(annotated_frame, f'Emotion: {emotion}', (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f'Activity: {activity}', (20, 95),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 200, 255), 2)

        cv2.imshow("Emotion + Activity Detection", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\n🛑 Exiting...")
            break

    cap.release()
    cv2.destroyAllWindows()
    if arduino:
        arduino.close()
        print("🔌 Arduino disconnected.")
    print(f"📄 Session saved to: {LOG_FILE}")

if __name__ == "__main__":
    run_combined_detection()