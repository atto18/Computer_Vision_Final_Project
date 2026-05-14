"""
STEP 1 — FRAME EXTRACTOR
========================
Run this first. Extracts frames from gesture videos.
Saves only frames where a hand is detected.

HOW TO RUN:
    python extract_frames.py
"""

import cv2
import mediapipe as mp
import os, sys, urllib.request

# ── CONFIG ────────────────────────────────────────────────────────────────
DATASET_ROOT = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset"
OUTPUT_ROOT  = r"C:\gesture_frames"
FRAME_SKIP   = 3
MIN_CONF     = 0.6

GESTURE_FOLDERS = [
    "2 fists walking forward",
    "2 fists walking left",
    "2 fists walking right",
    "cover protection",
    "open palms grenade",
    "Point_Shooting",
    "Reload gun",
]

# ── MEDIAPIPE SETUP (new Tasks API) ───────────────────────────────────────
MODEL_PATH = r"C:\hand_landmarker.task"
if not os.path.exists(MODEL_PATH):
    print("Downloading hand landmarker model (~25MB)...")
    urllib.request.urlretrieve(
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task",
        MODEL_PATH)
    print("Done.")

from mediapipe.tasks import python as _mpp
from mediapipe.tasks.python import vision as _mpv

_opts = _mpv.HandLandmarkerOptions(
    base_options=_mpp.BaseOptions(model_asset_path=MODEL_PATH),
    num_hands=2,
    min_hand_detection_confidence=MIN_CONF,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5,
    running_mode=_mpv.RunningMode.IMAGE
)
_detector = _mpv.HandLandmarker.create_from_options(_opts)

def hand_detected(frame_bgr):
    rgb   = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    res   = _detector.detect(mp_img)
    return len(res.hand_landmarks) > 0

# ── HELPERS ───────────────────────────────────────────────────────────────
def get_video_files(folder_path):
    exts = ('.mp4','.avi','.mov','.MOV','.MP4','.AVI','.mkv')
    return sorted([os.path.join(folder_path,f) for f in os.listdir(folder_path) if f.endswith(exts)])

def extract_from_video(video_path, out_folder, cls, vidx):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"    ⚠ Cannot open: {os.path.basename(video_path)}")
        return 0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps   = cap.get(cv2.CAP_PROP_FPS)
    print(f"    Video {vidx}: {os.path.basename(video_path)} ({total} frames @ {fps:.0f}fps)")
    saved, idx = 0, 0
    while True:
        ret, frame = cap.read()
        if not ret: break
        if idx % FRAME_SKIP == 0 and hand_detected(frame):
            fname = f"{cls}_v{vidx:02d}_f{idx:05d}.jpg".replace(" ","_")
            cv2.imwrite(os.path.join(out_folder, fname), frame)
            saved += 1
        idx += 1
    cap.release()
    return saved

# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    print("="*60)
    print("  GestureWar — Frame Extractor")
    print("="*60)
    if not os.path.exists(DATASET_ROOT):
        print(f"ERROR: Not found: {DATASET_ROOT}"); sys.exit(1)

    total_saved, class_counts = 0, {}

    for gesture in GESTURE_FOLDERS:
        gpath  = os.path.join(DATASET_ROOT, gesture)
        if not os.path.exists(gpath):
            print(f"⚠ Skipping (not found): {gesture}"); continue
        out_folder = os.path.join(OUTPUT_ROOT, gesture)
        os.makedirs(out_folder, exist_ok=True)
        print(f"\n📁 {gesture}")
        videos = get_video_files(gpath)
        if not videos:
            print("   ⚠ No videos found"); continue
        print(f"   {len(videos)} video(s)")
        cls_total = 0
        for i, vp in enumerate(videos, 1):
            saved = extract_from_video(vp, out_folder, gesture, i)
            print(f"      → {saved} frames saved")
            cls_total += saved
        class_counts[gesture] = cls_total
        total_saved += cls_total
        print(f"   ✅ Class total: {cls_total}")

    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    for cls, cnt in class_counts.items():
        status = "✅" if cnt >= 100 else "⚠ LOW"
        print(f"  {cls:<35} {cnt:>5}  {status}")
    print(f"  {'TOTAL':<35} {total_saved:>5}")
    print(f"\nFrames saved to: {OUTPUT_ROOT}")
    print("Next: python extract_features.py")

if __name__ == "__main__":
    main()

