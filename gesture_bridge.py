"""
GESTURE BRIDGE — Python → Unity
=================================
Run this ALONGSIDE Unity (not instead of it).
It reads your webcam, runs the gesture model,
and sends JSON commands to Unity via UDP every frame.

HOW TO RUN:
    1. Start Unity game first
    2. Run: python gesture_bridge.py
    3. Play the game with your gestures

REQUIRES:
    - Trained gesture model in gesture_models folder
    - hand_landmarker.task at C:\hand_landmarker.task
"""

import cv2
import socket
import json
import time
import sys
import os

# ── CONFIG ────────────────────────────────────────────────────────────────
UNITY_IP   = "127.0.0.1"
UNITY_PORT = 5065
SEND_FPS   = 30

MODELS_DIR = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset\gesture_models"

# ── SETUP ─────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("="*50)
print("  GestureWar — Python Bridge")
print("="*50)
print(f"Sending to Unity at {UNITY_IP}:{UNITY_PORT}")

# Load gesture predictor
try:
    from gesture_predictor import GesturePredictor
    predictor = GesturePredictor()
    print("✅ Gesture predictor loaded")
except Exception as e:
    print(f"⚠ Gesture predictor error: {e}")
    predictor = None

# Load head pose
try:
    import head_pose
    print("✅ Head pose loaded")
except Exception as e:
    print(f"⚠ Head pose error: {e}")
    head_pose = None

# UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Webcam
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("❌ No webcam found!")
    sys.exit(1)
print("✅ Webcam opened")
print()
print("Running. Press Q in the preview window to quit.")
print()

frame_time = 1.0 / SEND_FPS
last_time  = time.time()

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame = cv2.flip(frame, 1)

    # Gesture prediction
    gesture_data = {
        'gesture':    '',
        'confidence': 0.0,
        'action':     '',
        'hand_count': 0,
        'yaw':        0.0,
        'pitch':      0.0,
    }

    if predictor:
        result = predictor.predict(frame)
        gesture_data['gesture']    = result.get('gesture')    or ''
        gesture_data['confidence'] = result.get('confidence') or 0.0
        gesture_data['action']     = result.get('action')     or ''
        gesture_data['hand_count'] = result.get('hand_count') or 0

        # Draw on preview
        predictor.draw_overlay(frame, result)

    if head_pose:
        angles = head_pose.get_head_angles(frame)
        gesture_data['yaw']   = angles.get('yaw',   0.0)
        gesture_data['pitch'] = angles.get('pitch', 0.0)

        # Draw head pose on preview
        head_pose.draw_debug_overlay(frame, angles)

    # Send to Unity
    now = time.time()
    if now - last_time >= frame_time:
        last_time = now
        msg = json.dumps(gesture_data).encode('utf-8')
        sock.sendto(msg, (UNITY_IP, UNITY_PORT))

        # Print action if any
        if gesture_data['action']:
            print(f"  → {gesture_data['action']:15}  "
                  f"({gesture_data['gesture']}  {gesture_data['confidence']*100:.0f}%)")

    # Preview window
    cv2.imshow("GestureWar Bridge — Press Q to quit", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
sock.close()
print("Bridge stopped.")
