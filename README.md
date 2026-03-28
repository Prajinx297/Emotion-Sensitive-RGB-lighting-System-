# Emotion-Sensitive RGB Lighting System 🎭💡

## 📌 Overview

This project is an **AI-powered emotion and activity-aware lighting system** that dynamically adjusts RGB lighting based on the user's **facial emotions, detected activity, and stress level** in real time. It also provides **wellness feedback** through visual alerts and an OLED display.

---

## 🚀 Features

* Real-time **Emotion Detection** (Happy, Sad, Angry, Neutral, etc.)
* **Activity Recognition** (Gaming, Studying, Working, Relaxing)
* **Stress Level Calculation** (0–100 scale)
* **Adaptive RGB Lighting** based on emotion + activity
* **Breathing Light Effect** for high stress (calming mechanism)
* **Wellness Alert System** (suggests taking breaks)
* **OLED Display Interface** (Mood, Task, Timer, Stress bar)
* **Session Logging** (CSV file for analysis)
* **Stable Output** using rolling emotion history
* **Arduino Integration** via serial communication

---

## 🧠 System Architecture

1. Webcam captures real-time video
2. AI models process:

   * Emotion → FER (Facial Expression Recognition)
   * Activity → YOLO object detection
3. Stress score is computed from emotions
4. Data is encoded and sent to Arduino
5. Arduino:

   * Controls RGB LED
   * Displays data on OLED
   * Triggers alerts and effects

---

## 🛠️ Technologies Used

### Backend:

* **Python 3.x**
* **Flask** - Web server & API
* **OpenCV** - Video capture & processing
* **FER** - Facial Emotion Recognition
* **YOLOv8** - Object/Activity Detection
* **PySerial** - Arduino communication

### Frontend:

* **React 18** - UI framework
* **Vite** - Build tool & dev server
* **Tailwind CSS** - Styling
* **Chart.js** - Real-time data visualization
* **Proxy** - Backend API integration

### Hardware:

* Arduino (CH340 USB Serial)
* RGB LED (Common Anode)
* OLED Display (SSD1306)
* Webcam

---

## ⚙️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Prajinx297/Emotion-Sensitive-RGB-lighting-System-.git
cd Emotion-Sensitive-RGB-lighting-System-
```

### 2. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate   # Windows
```

### 3. Install Backend Dependencies

```bash
pip install opencv-python fer ultralytics pyserial flask numpy
```

### 4. Connect Hardware

* Connect Arduino via USB
* Verify COM port (typically `COM5` on Windows)
* Update `app.py` if needed:

```python
SERIAL_PORT = 'COM5'  # Change to your Arduino port
```

### 5. Start Backend

```bash
python app.py
```

**Backend will be running on:** `http://localhost:5000`

### 6. Start Frontend (New Terminal)

```bash
cd frontend
npm install
npm run dev
```

**Frontend will be running on:** `http://localhost:5173` (or next available port)

### 7. Open in Browser

Go to: **`http://localhost:5173`**

You should see:
- 📹 Live camera feed
- 🎭 Real-time emotion detection
- 📊 Activity & stress tracking
- 🎨 RGB color controls
- ⚙️ Patient mode toggle

### Production Build

```bash
cd frontend
npm run build
```

This creates `frontend/dist/` which Flask will serve automatically.

---

## 📁 Project Structure

```
Emotion-Sensitive-RGB-lighting-System-/
├── app.py                    # Flask backend server
├── emotion_monitor.py        # Standalone emotion monitor
├── emsrgbard.ino            # Arduino firmware
├── README.md                # Project documentation
├── frontend/                # React + Vite app
│   ├── src/
│   │   ├── App.jsx         # Main React component
│   │   ├── main.jsx        # Entry point
│   │   └── index.css       # Tailwind styles
│   ├── package.json        # Frontend dependencies
│   ├── vite.config.js      # Vite configuration
│   └── tailwind.config.js  # Tailwind configuration
└── templates/              # (Legacy) HTML templates
```

---

## 🔌 API Endpoints

All endpoints run on `http://localhost:5000/api/`

| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/api/frame` | GET | Get current camera frame (base64 JPEG) | `{"frame": "..."}` |
| `/api/stats` | GET | Get real-time emotion/activity/stress | `{emotion, activity, stress, ...}` |
| `/api/mode` | POST | Toggle patient/normal mode | `{"success": true}` |
| `/api/rgb` | POST | Send RGB color to Arduino | `{"success": true}` |

### Example Requests:

```javascript
// Get camera frame
fetch('http://localhost:5000/api/frame')
  .then(r => r.json())
  .then(d => console.log(d.frame))

// Toggle patient mode
fetch('http://localhost:5000/api/mode', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({patient_mode: true})
})

// Set RGB color
fetch('http://localhost:5000/api/rgb', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({r: 255, g: 100, b: 0})
})
```

---

## 🎨 Working Logic

### Emotion → Stress Mapping

* Negative emotions → Increase stress
* Positive emotions → Reduce stress

### Activity → Lighting Priority

* Gaming → Purple
* Working → Cyan
* Studying → Orange
* Idle → Based on emotion

### Stress Response

* Low stress → Normal lighting
* High stress → Breathing effect + alert

---

## 📊 Output

* Real-time annotated video feed
* RGB lighting changes dynamically
* OLED display shows:

  * Mood
  * Activity
  * Timer
  * Stress bar
* CSV log file for session tracking

---

## 🔥 Novelty of the Project

* Combines **emotion + activity + stress** into one system
* Not just reactive lighting — **context-aware smart environment**
* Includes **wellness intervention system**
* Real-time **AI + embedded system integration**

---

## 🔮 Future Improvements

* Add **voice assistant integration**
* Use **heart rate sensor** for better stress accuracy
* Mobile app dashboard for monitoring
* Smart home integration (IoT)
* Personalized lighting preferences using ML
* Offline emotion detection (local model)
* Advanced sleep detection

---

## 🐛 Troubleshooting

### Camera Not Showing
- Ensure backend is running: `python app.py`
- Wait 30-60 seconds for AI models to load on first run
- Check if webcam is accessible (not used by another app)

### Arduino Not Detected
- Check COM port: `Get-PnpDevice -Class Ports` (PowerShell)
- Update `SERIAL_PORT` in `app.py` to match your device
- Ensure Arduino drivers are installed

### Models Failing to Load
- First run downloads YOLO model (~350MB) - be patient
- Check internet connection for model downloads
- Ensure sufficient disk space (~2GB)

### Port Already in Use
- Change Vite port: `npm run dev -- --port 5175`
- Or kill process: `taskkill /F /IM node.exe /T`

---

## 📚 Quick Start Commands

```bash
# Terminal 1: Backend
cd Emotion-Sensitive-RGB-lighting-System-
python app.py

# Terminal 2: Frontend
cd Emotion-Sensitive-RGB-lighting-System-\frontend
npm run dev
```

Then open browser to `http://localhost:5173`

---

## 👨‍💻 Author

Prajin S
B.Tech Electronics and Computer Engineering
VIT Chennai

---

## 📄 License

This project is for educational and research purposes.
