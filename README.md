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

### Software:

* Python
* OpenCV
* FER (Emotion Detection)
* YOLOv8 (Object Detection)
* PySerial
* CSV Logging

### Hardware:

* Arduino
* RGB LED (Common Anode)
* OLED Display (SSD1306)
* Webcam

---

## ⚙️ Installation & Setup

### 1. Clone the Repository

```bash
git clone <your-repo-link>
cd emotion-rgb-system
```

### 2. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate   # Windows
```

### 3. Install Dependencies

```bash
pip install opencv-python fer ultralytics pyserial
```

### 4. Connect Hardware

* Connect Arduino via USB
* Update COM port in code:

```python
arduino = serial.Serial('COM12', 9600)
```

### 5. Run the Project

```bash
python main.py
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

---

## 👨‍💻 Author

Prajin S
B.Tech Electronics and Computer Engineering
VIT Chennai

---

## 📄 License

This project is for educational and research purposes.
