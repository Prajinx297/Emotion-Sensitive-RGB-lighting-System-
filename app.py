import cv2
import numpy as np
import threading
import time
import base64
from collections import deque
from datetime import datetime
from flask import Flask, render_template, Response, jsonify, request
from fer.fer import FER
from ultralytics import YOLO
import serial

app = Flask(__name__)

# ─────────────────────────────────────────────
#  CONFIGURATION & GLOBALS
# ─────────────────────────────────────────────
SERIAL_PORT           = 'COM12'
BAUD_RATE             = 9600
FRAME_SKIP_INTERVAL   = 3
HIGH_STRESS_THRESHOLD = 65
ALERT_COOLDOWN_SEC    = 45
EMOTION_HISTORY_LEN   = 5
YOLO_CONF             = 0.55

MOVEMENT_THRESHOLD    = 25
MOVEMENT_BUZZ_MIN_SEC = 2.0

# Global State
state = {
    "emotion": "neutral",
    "activity": "idle",
    "stress": 0,
    "patient_mode": False,
    "patient_moving": False,
    "activity_durations": {
        "gaming": 0,
        "working": 0,
        "studying": 0,
        "relaxing": 0,
        "idle": 0
    },
    "stress_history": []
}

# Thread synchronization
output_frame = None
lock = threading.Lock()

arduino = None
_last_alert_time  = 0
_last_sent_packet = None
_last_sent_time = 0

# Arduino initialization
try:
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"✅ Arduino connected on {SERIAL_PORT}")
except Exception as e:
    print(f"⚠️  Arduino not found ({e}) — running in display-only mode")
    arduino = None

def dominant_emotion(history: deque) -> str:
    return max(set(history), key=history.count) if history else "neutral"

def compute_stress(e: dict) -> int:
    if not e: return 0
    stressed = e.get('angry', 0)*0.40 + e.get('fear', 0)*0.35 + e.get('disgust', 0)*0.25
    calm     = e.get('happy',  0)*0.50 + e.get('surprise', 0)*0.20 + e.get('neutral', 0)*0.30
    return max(0, min(100, int((stressed - calm*0.5 + 1) / 2 * 100)))

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

def send_to_arduino(arduino, emotion: str, activity: str, stress: int,
                    patient_mode: bool, patient_moving: bool = False):
    global _last_alert_time, _last_sent_packet, _last_sent_time

    if patient_mode:
        act = "DANGER" if patient_moving else "STABLE"
    else:
        act = activity.upper()

    t_str = datetime.now().strftime('%H:%M')
    packet = f"E:{emotion.upper()},A:{act},S:{stress},T:{t_str}"

    now = time.time()
    if packet == _last_sent_packet and (now - _last_sent_time) < 3.0:
        return
    
    _last_sent_packet = packet
    _last_sent_time = now

    with lock:
        if arduino:
            arduino.write((packet + '\n').encode())

    if not patient_mode:
        if stress >= HIGH_STRESS_THRESHOLD and (now - _last_alert_time) > ALERT_COOLDOWN_SEC:
            with lock:
                if arduino:
                    arduino.write(b"ALERT\n")
            _last_alert_time = now

class MovementDetector:
    def __init__(self):
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=100, varThreshold=50, detectShadows=False)
        self.consecutive_frames = 0
        self.last_moved_time = 0
        
    def update(self, frame) -> bool:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        fg_mask = self.bg_subtractor.apply(gray)
        _, thresh = cv2.threshold(fg_mask, 25, 255, cv2.THRESH_BINARY)
        
        movement_area = cv2.countNonZero(thresh)
        if movement_area > 5000:
            self.consecutive_frames += 1
            if self.consecutive_frames > 2:
                self.last_moved_time = time.time()
        else:
            self.consecutive_frames = 0
            
        # Hold "moving" state for 2.0 seconds after last significant movement
        return (time.time() - self.last_moved_time) < 2.0

def process_camera():
    global output_frame, state
    
    emotion_hist = deque(maxlen=EMOTION_HISTORY_LEN)
    move_det     = MovementDetector()

    print("⏳ Loading models…")
    try:
        emotion_detector = FER(mtcnn=True)
        activity_model   = YOLO('yolov8m.pt')
        print("✅ Models ready")
    except Exception as e:
        print(f"❌ Error loading AI models: {e}")
        return

    # Try different backends (DSHOW is best for Windows)
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap = cv2.VideoCapture(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    frame_idx = 0
    last_act_time = time.time()
    missing_face_counter = 0

    while True:
        try:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("⚠️ Camera frame blank! Waiting to reconnect...")
                time.sleep(1.0)
                # Try to re-init camera natively
                cap.release()
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(1)
                continue

            frame = cv2.flip(frame, 1)

            now = time.time()
            if now - last_act_time >= 1.0:
                with lock:
                    if not state["patient_mode"] and state["activity"] in state["activity_durations"]:
                        state["activity_durations"][state["activity"]] += 1
                    
                    time_str = datetime.now().strftime('%H:%M:%S')
                    state["stress_history"].append({"time": time_str, "stress": state["stress"]})
                    if len(state["stress_history"]) > 60:
                        state["stress_history"].pop(0)

                last_act_time = now

            if frame_idx % FRAME_SKIP_INTERVAL == 0:
                with lock:
                    is_patient = state["patient_mode"]

                if is_patient:
                    p_moving = move_det.update(frame)
                    with lock:
                        state["patient_moving"] = p_moving
                        state["activity"] = "moving" if p_moving else "stable"
                    send_to_arduino(arduino, state["emotion"], state["activity"], state["stress"], True, patient_moving=p_moving)
                    
                    if p_moving:
                        label, color = "PATIENT MOVING!", (0, 0, 255)
                    else:
                        label, color = "PATIENT STABLE", (0, 255, 0)
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 1.4, 3)
                    h, w = frame.shape[:2]
                    x, y = (w - tw) // 2, (h + th) // 2
                    pad = 14
                    cv2.rectangle(frame, (x-pad, y-th-pad), (x+tw+pad, y+pad), (0,0,0), -1)
                    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_DUPLEX, 1.4, color, 3, cv2.LINE_AA)
                else:
                    detections = emotion_detector.detect_emotions(frame)
                    if detections:
                        raw = detections[0]['emotions']
                        emotion_hist.append(max(raw, key=raw.get))
                        emo = dominant_emotion(emotion_hist)
                        str_val = compute_stress(raw)
                        missing_face_counter = 0
                    else:
                        missing_face_counter += 1
                        if missing_face_counter > 15:
                            emo = "neutral"
                            str_val = 0
                        else:
                            emo = state["emotion"]
                            str_val = state["stress"]

                    yolo_results = activity_model.predict(source=frame, conf=YOLO_CONF, verbose=False)
                    act = "idle"
                    if yolo_results:
                        names = activity_model.names
                        objects = [names[int(c)] for r in yolo_results for c in r.boxes.cls]
                        act = classify_activity(objects)
                        frame = yolo_results[0].plot()

                    with lock:
                        state["emotion"] = emo
                        state["activity"] = act
                        state["stress"] = str_val
                        
                    send_to_arduino(arduino, emo, act, str_val, False, patient_moving=False)

            with lock:
                output_frame = frame.copy()

            frame_idx += 1
            
        except Exception as e:
            print(f"⚠️ Error inside camera loop: {e}")
            time.sleep(1.0)

threading.Thread(target=process_camera, daemon=True).start()

def generate_video():
    global output_frame, lock
    
    # Pre-generate a loading frame so Chrome doesn't timeout the image tag!
    loading_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(loading_frame, "Loading AI...", (220, 240), 
                cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 2)
    _, loading_jpg = cv2.imencode(".jpg", loading_frame)
    loading_bytes = bytearray(loading_jpg)

    while True:
        frame_to_yield = None
        with lock:
            if output_frame is not None:
                frame_to_yield = output_frame.copy()

        if frame_to_yield is None:
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
                   loading_bytes + b'\r\n')
            time.sleep(0.5)
            continue
            
        flag, encoded_img = cv2.imencode(".jpg", frame_to_yield)
        if not flag:
            continue
        
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
               bytearray(encoded_img) + b'\r\n')
        time.sleep(0.05)

@app.route("/api/frame")
def api_frame():
    global output_frame, lock
    with lock:
        if output_frame is None:
            loading = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(loading, "Loading Camera...", (180, 240), 
                        cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 2)
            _, img = cv2.imencode(".jpg", loading)
            return jsonify({"frame": base64.b64encode(img).decode('utf-8')})
            
        view = output_frame.copy()
        
    if view.std() < 3.0:
        cv2.putText(view, "HARDWARE LENS IS BLACK", (100, 240), 
                    cv2.FONT_HERSHEY_DUPLEX, 1.0, (0, 0, 255), 3)
                    
    flag, encoded_img = cv2.imencode(".jpg", view)
    if not flag:
        return jsonify({"frame": None})
    return jsonify({"frame": base64.b64encode(encoded_img).decode('utf-8')})

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/video_feed")
def video_feed():
    return Response(generate_video(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/stats")
def api_stats():
    with lock:
        return jsonify(state)

@app.route("/api/mode", methods=["POST"])
def api_mode():
    data = request.json
    mode = data.get("patient_mode", False)
    with lock:
        state["patient_mode"] = mode
        if mode:
            state["emotion"] = "neutral"
            state["stress"] = 0
            state["activity"] = "stable"
            state["stress_history"].clear()
            state["activity_durations"] = {
                "gaming": 0,
                "working": 0,
                "studying": 0,
                "relaxing": 0,
                "idle": 0
            }
        if arduino:
            arduino.write(b"PATIENT_ON\n" if mode else b"PATIENT_OFF\n")
            
    # clear the last sent packet so the background thread forces an immediate refresh
    global _last_sent_packet
    _last_sent_packet = None
    
    return jsonify({"success": True})

@app.route("/api/rgb", methods=["POST"])
def api_rgb():
    data = request.json
    with lock:
        if arduino:
            if data.get('auto'):
                arduino.write(b"AUTO_COLOR\n")
            else:
                r, g, b = data.get('r', 0), data.get('g', 0), data.get('b', 0)
                arduino.write(f"RGB,{r},{g},{b}\n".encode())
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
