"""
HealthOS Posture Monitor — AI Engine
Flask + MediaPipe pose detection backend.
Runs a single continuous camera loop in a daemon thread.
All processing is 100% offline / on-device.
"""

import matplotlib
matplotlib.use('Agg')

import sys
import os

# Handle frozen environment (PyInstaller)
if getattr(sys, 'frozen', False):
    # Add the bundle directory to sys.path to find data-bundled packages
    bundle_dir = sys._MEIPASS
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

from flask import Flask, jsonify
from flask_cors import CORS
import cv2
import mediapipe as mp
import math
import threading
import time
import logging

# Robust MediaPipe imports for PyInstaller
try:
    from mediapipe.python.solutions import pose as mp_pose
    from mediapipe.python.solutions import drawing_utils as mp_drawing
except ImportError:
    try:
        mp_pose = mp.solutions.pose
        mp_drawing = mp.solutions.drawing_utils
    except AttributeError:
        # Final fallback for some frozen environments
        import mediapipe.python.solutions.pose as mp_pose
        import mediapipe.python.solutions.drawing_utils as mp_drawing

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("posture-engine")

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)  # allow Tauri webview (different origin) to reach the API

# ── MediaPipe Pose (lightweight, CPU-only) ─────────────────────────────────────
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=0,          # 0 = lite model → lowest CPU usage
    smooth_landmarks=True,
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# ── Shared state (written by camera thread, read by Flask) ─────────────────────
_lock = threading.Lock()
_latest: dict = {"status": "starting", "angle": None}
_latest_frame = b''


def _set_result(status: str, angle=None) -> None:
    with _lock:
        _latest["status"] = status
        _latest["angle"] = round(angle, 2) if angle is not None else None


def _get_result() -> dict:
    with _lock:
        return dict(_latest)


# ── Angle calculation ──────────────────────────────────────────────────────────
def calculate_angle(ear: tuple, shoulder: tuple, hip: tuple) -> float:
    """
    Returns the deviation (in degrees) from a perfectly straight 180° posture
    formed by the ear → shoulder → hip vectors.
    0° = perfectly straight. Higher = more slouch.
    """
    angle = math.degrees(
        math.atan2(hip[1] - shoulder[1], hip[0] - shoulder[0])
        - math.atan2(ear[1] - shoulder[1], ear[0] - shoulder[0])
    )
    angle = abs(angle)
    if angle > 180:
        angle = 360 - angle

    # 180 is upright. Deviation from 180 is our slouch angle.
    return abs(180 - angle)


# ── Camera loop (runs in a daemon thread) ─────────────────────────────────────
CAMERA_INDEX   = 0
FRAME_WIDTH    = 640
FRAME_HEIGHT   = 480
LOOP_DELAY_SEC = 0.10   # ~10 FPS → smooth enough video, reasonable CPU
BAD_ANGLE_DEG  = 10.0   # threshold: angle > this → "bad" posture (stricter, requires 90+ score)


def camera_loop() -> None:
    log.info("Camera loop starting …")

    # Keep retrying if the camera is not available at startup
    cap = None
    while cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            log.warning("Camera not available — retrying in 3 s …")
            _set_result("camera_error")
            time.sleep(3)
            continue

    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    log.info("Camera opened at %dx%d", FRAME_WIDTH, FRAME_HEIGHT)

    while True:
        ret, frame = cap.read()
        if not ret:
            log.warning("Failed to read frame — camera may have disconnected")
            _set_result("camera_error")
            cap.release()
            cap = cv2.VideoCapture(CAMERA_INDEX)
            time.sleep(1)
            continue

        # MediaPipe expects RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Prevent MediaPipe from writing back into the frame buffer
        frame_rgb.flags.writeable = False
        results = pose.process(frame_rgb)

        if not results.pose_landmarks:
            _set_result("no_person")
        else:
            lm = results.pose_landmarks.landmark

            ear      = lm[mp_pose.PoseLandmark.LEFT_EAR.value]
            shoulder = lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            hip      = lm[mp_pose.PoseLandmark.LEFT_HIP.value]

            # Confidence check: MediaPipe hallucinates points off-screen.
            # We strictly discard if visibility is low, OR if the predicted Y coordinates
            # fall near or below the bottom of the camera view (> 0.85).
            if ear.visibility < 0.65 or shoulder.visibility < 0.65 or shoulder.y > 0.85 or ear.y > 0.85:
                _set_result("no_person")
            else:
                # Use normalised (x, y) coordinates — sufficient for angle calc
                ear_pt      = (ear.x,      ear.y)
                shoulder_pt = (shoulder.x, shoulder.y)
                hip_pt      = (hip.x,      hip.y)

                angle = calculate_angle(ear_pt, shoulder_pt, hip_pt)
                status = "bad" if angle > BAD_ANGLE_DEG else "good"
                _set_result(status, angle)

                # Draw skeleton with colour based on status
                color = (0, 255, 0) if status == "good" else (0, 0, 255) # BGR
                landmark_spec = mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=4)
                connection_spec = mp_drawing.DrawingSpec(color=color, thickness=2)

                mp_drawing.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=landmark_spec,
                    connection_drawing_spec=connection_spec
                )

        # encode frame for streaming
        ret_encoding, buffer = cv2.imencode('.jpg', frame)
        if ret_encoding:
            global _latest_frame
            with _lock:
                _latest_frame = buffer.tobytes()

        time.sleep(LOOP_DELAY_SEC)


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    return {"service": "HealthOS Posture Engine", "version": "1.0.0"}


@app.get("/posture")
def posture():
    """
    Returns:
        {
            "status": "good" | "bad" | "no_person" | "camera_error" | "starting",
            "angle":  <float | null>
        }
    """
    return jsonify(_get_result())


@app.get("/health")
def health():
    return {"ok": True}


def generate_frames():
    while True:
        with _lock:
            frame = _latest_frame
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(LOOP_DELAY_SEC)

@app.route('/video_feed')
def video_feed():
    from flask import Response
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Start camera thread BEFORE accepting requests
    t = threading.Thread(target=camera_loop, daemon=True, name="camera-loop")
    t.start()

    log.info("Starting Flask server on http://127.0.0.1:5000")
    # use_reloader=False is critical — reloader spawns a second process that
    # would open the camera twice and deadlock.
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)