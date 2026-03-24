# emotion_activity_arduino.py

import cv2
from fer import FER
from ultralytics import YOLO
import serial
import time

# ----------------- SETUP -----------------
# Direct USB Serial connection to Arduino
try:
    arduino = serial.Serial('COM12', 9600, timeout=1)
    time.sleep(2)
    print("✅ Arduino connected via USB Serial.")
except Exception as e:
    print(f"⚠️ Arduino connection failed: {e}")
    arduino = None

# Load models
print("⏳ Loading models...")
emotion_detector = FER(mtcnn=True)
activity_model = YOLO('yolov8m.pt')
print("✅ Models loaded successfully.\n")

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

# ----------------- RGB COLOR MAPPING -----------------
def send_to_arduino(emotion, activity):

    if not arduino:
        return

    emotion_codes = {
        'happy': '00',
        'sad': '01',
        'angry': '10',
        'neutral': '11'
    }

    activity_codes = {
        'gaming': '00',
        'working': '01',
        'studying': '10',
        'idle': '11'
    }

    emotion_code = emotion_codes.get(emotion, '11')
    activity_code = activity_codes.get(activity, '11')

    data = f"{emotion_code},{activity_code}\n"

    arduino.write(data.encode())

    print(f"Emotion: {emotion:8s} → {emotion_code} | Activity: {activity:8s} → {activity_code} | Sent: {data.strip()}")

# ----------------- MAIN FUNCTION -----------------
def run_combined_detection():

    cap = cv2.VideoCapture(0)
    cap.set(3, 640)
    cap.set(4, 480)

    if not cap.isOpened():
        print("❌ Error: Cannot open webcam.")
        return

    print("🎥 Emotion + Activity Detection Started.")
    print("Press 'q' to quit.\n")

    frame_skip = 0
    emotion = "neutral"
    activity = "idle"

    while True:

        ret, frame = cap.read()

        if not ret:
            print("❌ Error: Frame not captured.")
            break

        frame = cv2.flip(frame, 1)

        if frame_skip % 3 == 0:

            # Emotion Detection
            emotion_results = emotion_detector.detect_emotions(frame)

            if emotion_results:
                emotions = emotion_results[0]['emotions']
                emotion = max(emotions, key=emotions.get)

            # Activity Detection
            results = activity_model.predict(source=frame, conf=0.55, verbose=False)
            names = activity_model.names

            detected_objects = [names[int(c)] for r in results for c in r.boxes.cls]

            activity = classify_activity(detected_objects)

            send_to_arduino(emotion, activity)

        frame_skip += 1

        annotated_frame = results[0].plot()

        cv2.putText(annotated_frame, f'Emotion: {emotion}', (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 2)

        cv2.putText(annotated_frame, f'Activity: {activity}', (20, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 200, 255), 2)

        cv2.imshow("Emotion + Activity Detection", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\n🛑 Exiting Program...")
            break

    cap.release()
    cv2.destroyAllWindows()

    if arduino:
        arduino.close()
        print("🔌 Arduino disconnected.")


# ----------------- RUN -----------------
if __name__ == "__main__":
    run_combined_detection()