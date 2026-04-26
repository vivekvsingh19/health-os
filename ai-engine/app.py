"""
HealthOS Posture Monitor — AI Engine (Tasks API Edition)
Flask + MediaPipe Tasks pose detection backend.
Works with modern MediaPipe (0.10+).
"""

import matplotlib
matplotlib.use('Agg')

import sys
import os
import cv2
import mediapipe as mp
import numpy as np
import math
import threading
import time
import logging
from flask import Flask, jsonify
from flask_cors import CORS

# Handle frozen environment (PyInstaller)
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)
    MODEL_PATH = os.path.join(bundle_dir, "pose_landmarker.task")
else:
    MODEL_PATH = "pose_landmarker.task"

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("posture-engine")

# ── MediaPipe Tasks Setup ──────────────────────────────────────────────────────
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    output_segmentation_masks=False
)
detector = vision.PoseLandmarker.create_from_options(options)

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ── Shared state ───────────────────────────────────────────────────────────────
_lock = threading.Lock()
_latest: dict = {"status": "starting", "angle": None}
_latest_frame = b''

def _set_result(status: str, angle: float = None):
    with _lock:
        _latest["status"] = status
        _latest["angle"] = round(angle, 1) if angle is not None else None

def _get_result():
    with _lock:
        return _latest.copy()

# ── Posture Logic ─────────────────────────────────────────────────────────────
BAD_ANGLE_THRESHOLD = 20  # degrees of deviation from straight
LOOP_DELAY_SEC = 0.033 # ~30 FPS

# Landmark indices for pose
NOSE = 0
L_SHOULDER = 11
R_SHOULDER = 12
L_HIP = 23
R_HIP = 24
L_EAR = 7
R_EAR = 8

def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    
    # Calculate vectors
    ba = a - b
    bc = c - b
    
    # Calculate cosine of angle
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
    angle_deg = np.degrees(angle)
    
    # We want deviation from 180 degrees
    # If angle_deg is 180, deviation is 0. If angle_deg is 150, deviation is 30.
    deviation = abs(180 - angle_deg)
    return deviation

def draw_landmarks(frame, landmarks):
    """Simple manual drawing of pose landmarks since drawing_utils is legacy."""
    h, w, _ = frame.shape
    # Draw connections (simplified set)
    connections = [
        (11, 12), (11, 23), (12, 24), (23, 24), # Torso
        (7, 11), (8, 12), # Ear to Shoulder
    ]
    
    # Extract points
    pts = {}
    for i, lm in enumerate(landmarks):
        pts[i] = (int(lm.x * w), int(lm.y * h))
        
    color = (0, 255, 0) # Default green
    for start_idx, end_idx in connections:
        if start_idx in pts and end_idx in pts:
            cv2.line(frame, pts[start_idx], pts[end_idx], color, 2)
    
    for idx in [7, 8, 11, 12, 23, 24]: # Draw key points
        if idx in pts:
            cv2.circle(frame, pts[idx], 4, (255, 255, 0), -1)

def camera_loop():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        log.error("Could not open camera.")
        _set_result("camera_error")
        return

    log.info("Camera opened.")
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            _set_result("camera_error")
            break

        # Convert for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        
        # Detector processing
        timestamp_ms = int(time.time() * 1000)
        results = detector.detect_for_video(mp_image, timestamp_ms)

        if not results.pose_landmarks:
            _set_result("no_person")
        else:
            # We use the first person detected
            landmarks = results.pose_landmarks[0]
            
            # Posture logic (Side view preferred)
            # Find Ear, Shoulder, and Hip on the same side
            l_vis = landmarks[L_EAR].visibility > 0.5 and landmarks[L_SHOULDER].visibility > 0.5
            r_vis = landmarks[R_EAR].visibility > 0.5 and landmarks[R_SHOULDER].visibility > 0.5
            
            target_pts = None
            if l_vis:
                target_pts = (
                    (landmarks[L_EAR].x, landmarks[L_EAR].y),
                    (landmarks[L_SHOULDER].x, landmarks[L_SHOULDER].y),
                    (landmarks[L_HIP].x, landmarks[L_HIP].y)
                )
            elif r_vis:
                target_pts = (
                    (landmarks[R_EAR].x, landmarks[R_EAR].y),
                    (landmarks[R_SHOULDER].x, landmarks[R_SHOULDER].y),
                    (landmarks[R_HIP].x, landmarks[R_HIP].y)
                )

            if target_pts:
                deviation = calculate_angle(*target_pts)
                status = "bad" if deviation > BAD_ANGLE_THRESHOLD else "good"
                _set_result(status, deviation)
                
                # Draw
                draw_landmarks(frame, landmarks)
            else:
                _set_result("no_person")

        # Encode for streaming
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            global _latest_frame
            with _lock:
                _latest_frame = buffer.tobytes()

        time.sleep(LOOP_DELAY_SEC)

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    return {"service": "HealthOS Posture Engine", "version": "2.0.0"}

@app.get("/posture")
def posture():
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

if __name__ == "__main__":
    t = threading.Thread(target=camera_loop, daemon=True)
    t.start()
    log.info("Starting Flask server on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)