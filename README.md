# 🧘 HealthOS Posture Monitor

> **Privacy-first, AI-powered posture monitoring that runs silently on your desktop.**

HealthOS uses on-device AI (MediaPipe) to analyze your posture in real-time through your webcam. No data ever leaves your computer. When your posture drops, the app pops up to coach you back into alignment — then disappears when you're sitting correctly.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **Real-time AI Analysis** | MediaPipe pose detection running 100% offline on your CPU |
| 📊 **Posture Score (0–100)** | Intuitive score showing exactly how well you're sitting |
| 🟢🔴 **Visual Skeleton Overlay** | Green when good, red when slouching — drawn directly on your video feed |
| 🧘 **Smart Coaching** | Context-aware instructions: "Straighten your back", "Lift your chest" |
| 👻 **Auto Popup / Dismiss** | Bad posture for 1 min → window appears. Fix it → window auto-hides |
| 🔔 **Desktop Notifications** | Non-intrusive alerts with cooldown protection |
| 🖥️ **System Tray** | Minimize to tray, runs silently in the background |
| 🚀 **Autostart** | Launches automatically when you boot your computer |
| 🪑 **Sitting Timer** | Tracks how long you've been sitting, reminds you to take breaks at 60 min |
| 🔒 **100% Private** | All processing happens on-device. Zero cloud. Zero tracking. |

---

## 🖼️ Screenshots

The app overlays your live webcam feed with:
- **Top Left**: Posture Score (0–100) in green/red
- **Top Right**: Sitting duration timer
- **Bottom Center**: Coaching instructions
- **On Video**: Color-coded skeleton (green = good, red = bad)

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| **AI Engine** | Python, Flask, OpenCV, MediaPipe |
| **Desktop App** | Tauri 2 (Rust) |
| **Frontend** | SvelteKit |
| **Notifications** | Tauri Plugin Notification |
| **System Tray** | Tauri Tray Icon API |
| **Autostart** | Tauri Plugin Autostart |

---

## 📦 Prerequisites

- **Python 3.8+** with `pip`
- **Node.js 18+** with `npm`
- **Rust** (install via [rustup.rs](https://rustup.rs))
- **Webcam** (built-in or USB)
- **Linux**: `sudo apt install libwebkit2gtk-4.1-dev build-essential libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev`

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/your-username/health-os.git
cd health-os
```

### 2. Set up the Python backend (first time only)
```bash
cd ai-engine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 3. Install frontend dependencies
```bash
npm install
```

### 4. Run in development mode
```bash
npm run tauri dev
```

The app will **automatically start the Python AI backend** — no need to run it separately!

### 5. Build for production
```bash
npm run tauri build
```

This generates an installable `.deb` and `.AppImage` in `src-tauri/target/release/bundle/`.

---

## 🏗️ Project Structure

```
health-os/
├── ai-engine/              # Python AI backend
│   ├── app.py              # Flask server + MediaPipe pose detection
│   ├── requirements.txt    # Python dependencies
│   └── venv/               # Python virtual environment
├── src/                    # SvelteKit frontend
│   └── routes/
│       └── +page.svelte    # Main UI (score, timer, coaching)
├── src-tauri/              # Tauri desktop wrapper
│   ├── src/lib.rs          # Rust core (tray, autostart, backend launcher)
│   ├── tauri.conf.json     # App configuration
│   ├── capabilities/       # Permission grants
│   └── icons/              # App icons (all sizes)
├── start-backend.sh        # Manual backend launcher (optional)
├── package.json            # Node.js dependencies
└── README.md               # You are here!
```

---

## ⚙️ Configuration

### Adjusting Posture Sensitivity

In `ai-engine/app.py`, change the threshold:

```python
BAD_ANGLE_DEG = 10.0   # Lower = stricter (requires near-perfect posture)
```

### Adjusting Auto-Popup Delay

In `src/routes/+page.svelte`, change:

```javascript
const BAD_POPUP_DELAY_MS = 60_000;  // 1 minute (change to 30_000 for 30s)
```

### Adjusting Break Reminder

```javascript
const BREAK_INTERVAL_MS = 60 * 60 * 1000;  // 60 minutes
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License.

---

## 🙏 Acknowledgments

- [MediaPipe](https://mediapipe.dev/) — On-device ML framework by Google
- [Tauri](https://tauri.app/) — Lightweight desktop app framework
- [SvelteKit](https://kit.svelte.dev/) — Web framework
- [OpenCV](https://opencv.org/) — Computer vision library

---

**Built with ❤️ for better posture and healthier work habits.**
# health-os
