"""
STEP 2 — FEATURE EXTRACTOR
===========================
Run after extract_frames.py.
Builds dataset.csv from extracted frames.

HOW TO RUN:
    python extract_features.py
"""

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
import os, sys, math, urllib.request

# ── CONFIG ────────────────────────────────────────────────────────────────
DATASET_ROOT = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset"
FRAMES_ROOT  = r"C:\gesture_frames"
OUTPUT_CSV   = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset\gesture_dataset.csv"

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
    min_hand_detection_confidence=0.6,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5,
    running_mode=_mpv.RunningMode.IMAGE
)
_detector = _mpv.HandLandmarker.create_from_options(_opts)

# ── FEATURE ENGINEERING ───────────────────────────────────────────────────
def angle_between(a, b, c):
    ba = np.array([a.x-b.x, a.y-b.y, a.z-b.z])
    bc = np.array([c.x-b.x, c.y-b.y, c.z-b.z])
    cos = np.dot(ba,bc)/(np.linalg.norm(ba)*np.linalg.norm(bc)+1e-7)
    return math.degrees(math.acos(np.clip(cos,-1,1)))

def distance(a, b):
    return math.sqrt((a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2)

def features_from_hand(lm):
    f = []
    for trio in [(1,2,3),(2,3,4),(0,1,2),
                 (5,6,7),(6,7,8),(0,5,6),
                 (9,10,11),(10,11,12),(0,9,10),
                 (13,14,15),(14,15,16),(0,13,14),
                 (17,18,19),(18,19,20),(0,17,18)]:
        f.append(angle_between(lm[trio[0]], lm[trio[1]], lm[trio[2]]))
    for tip in [4,8,12,16,20]:
        f.append(distance(lm[tip], lm[0]))
    palm = distance(lm[0], lm[9])
    tips = np.array([[lm[t].x, lm[t].y] for t in [4,8,12,16,20]])
    spread = np.max(np.linalg.norm(tips[:,None]-tips[None,:], axis=2))
    f.append(spread/(palm+1e-7))
    return np.array(f, dtype=np.float32)  # 21 values

def process_image(img_path):
    img = cv2.imread(img_path)
    if img is None: return None
    rgb    = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    res    = _detector.detect(mp_img)
    if not res.hand_landmarks: return None

    hands_lm   = res.hand_landmarks
    handedness = res.handedness

    left_f  = np.zeros(21, dtype=np.float32)
    right_f = np.zeros(21, dtype=np.float32)
    left_x  = right_x = 0.5

    for i, lm_list in enumerate(hands_lm[:2]):
        f      = features_from_hand(lm_list)
        wrist_x= lm_list[0].x
        label  = handedness[i][0].category_name if i < len(handedness) else ('Left' if wrist_x<0.5 else 'Right')
        if label == 'Left':
            left_f, left_x  = f, wrist_x
        else:
            right_f, right_x = f, wrist_x

    return np.concatenate([left_f, right_f, [left_x, right_x, float(len(hands_lm))]])

# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    print("="*60)
    print("  GestureWar — Feature Extractor")
    print("="*60)
    if not os.path.exists(FRAMES_ROOT):
        print("ERROR: frames folder not found. Run extract_frames.py first."); sys.exit(1)

    all_rows, all_labels, class_counts = [], [], {}

    for gesture in GESTURE_FOLDERS:
        gpath = os.path.join(FRAMES_ROOT, gesture)
        if not os.path.exists(gpath):
            print(f"⚠ Skipping: {gesture}"); continue
        imgs = [f for f in os.listdir(gpath) if f.lower().endswith(('.jpg','.jpeg','.png'))]
        if not imgs:
            print(f"⚠ No images: {gesture}"); continue
        print(f"📁 {gesture}: {len(imgs)} frames", end="", flush=True)
        ok, skip = 0, 0
        for img_file in imgs:
            feat = process_image(os.path.join(gpath, img_file))
            if feat is not None:
                all_rows.append(feat); all_labels.append(gesture); ok += 1
            else:
                skip += 1
        class_counts[gesture] = ok
        print(f" → {ok} extracted, {skip} skipped")

    if not all_rows:
        print("ERROR: No features extracted."); sys.exit(1)

    feat_dim  = len(all_rows[0])
    cols      = [f"f{i:03d}" for i in range(feat_dim)] + ["label"]
    df        = pd.DataFrame(np.column_stack([np.array(all_rows), all_labels]), columns=cols)
    df.to_csv(OUTPUT_CSV, index=False)

    print("\n" + "="*60)
    total = sum(class_counts.values())
    for cls, cnt in class_counts.items():
        print(f"  {cls:<35} {cnt:>5}  {'✅' if cnt>=100 else '⚠'}")
    print(f"  {'TOTAL':<35} {total:>5}")
    print(f"\nFeature dim : {feat_dim}")
    print(f"CSV saved   : {OUTPUT_CSV}")
    print("Next: python train_gesture_model.py")

if __name__ == "__main__":
    main()
