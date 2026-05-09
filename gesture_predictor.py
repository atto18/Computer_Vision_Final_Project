"""
GESTURE CLASSIFIER — REAL-TIME INFERENCE
==========================================
Loads trained MLP and runs live gesture prediction.
Import GesturePredictor in the game loop.
"""

import cv2
import mediapipe as mp
import numpy as np
import torch
import torch.nn as nn
import pickle, os, math, urllib.request
from collections import deque

# ── CONFIG ────────────────────────────────────────────────────────────────
DATASET_ROOT = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset"
MODELS_DIR   = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset\gesture_models"
MODEL_PATH   = os.path.join(MODELS_DIR, "gesture_model.pth")
SCALER_PATH  = os.path.join(MODELS_DIR, "scaler.pkl")
ENCODER_PATH = os.path.join(MODELS_DIR, "label_encoder.pkl")

CONFIDENCE_THRESHOLD = 0.55
DEBOUNCE_FRAMES      = 3
RELOAD_HOLD_FRAMES   = 15

# ── MEDIAPIPE SETUP ───────────────────────────────────────────────────────
_MODEL_PATH = r"C:\hand_landmarker.task"
if not os.path.exists(_MODEL_PATH):
    print("Downloading hand landmarker model...")
    urllib.request.urlretrieve(
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task",
        _MODEL_PATH)

from mediapipe.tasks import python as _mpp
from mediapipe.tasks.python import vision as _mpv

# ── MODEL ─────────────────────────────────────────────────────────────────
class GestureClassifier(nn.Module):
    def __init__(self, input_dim, num_classes, hidden1=128, hidden2=64, dropout=0.3):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden1), nn.BatchNorm1d(hidden1), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden1, hidden2),  nn.BatchNorm1d(hidden2), nn.ReLU(), nn.Dropout(dropout*0.7),
            nn.Linear(hidden2, num_classes)
        )
    def forward(self, x): return self.network(x)

# ── FEATURE HELPERS ───────────────────────────────────────────────────────
def _angle(a,b,c):
    ba=np.array([a.x-b.x,a.y-b.y,a.z-b.z]); bc=np.array([c.x-b.x,c.y-b.y,c.z-b.z])
    return math.degrees(math.acos(np.clip(np.dot(ba,bc)/(np.linalg.norm(ba)*np.linalg.norm(bc)+1e-7),-1,1)))

def _dist(a,b): return math.sqrt((a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2)

def _hand_features(lm):
    f=[]
    for t in [(1,2,3),(2,3,4),(0,1,2),(5,6,7),(6,7,8),(0,5,6),
              (9,10,11),(10,11,12),(0,9,10),(13,14,15),(14,15,16),(0,13,14),
              (17,18,19),(18,19,20),(0,17,18)]:
        f.append(_angle(lm[t[0]],lm[t[1]],lm[t[2]]))
    for tip in [4,8,12,16,20]: f.append(_dist(lm[tip],lm[0]))
    palm=_dist(lm[0],lm[9]); tips=np.array([[lm[t].x,lm[t].y] for t in [4,8,12,16,20]])
    f.append(np.max(np.linalg.norm(tips[:,None]-tips[None,:],axis=2))/(palm+1e-7))
    return np.array(f,dtype=np.float32)

def _build_vector(res):
    lf=np.zeros(21,dtype=np.float32); rf=np.zeros(21,dtype=np.float32); lx=rx=0.5
    for i,lm in enumerate(res.hand_landmarks[:2]):
        f=_hand_features(lm); wx=lm[0].x
        label=res.handedness[i][0].category_name if i<len(res.handedness) else ('Left' if wx<0.5 else 'Right')
        if label=='Left': lf,lx=f,wx
        else:             rf,rx=f,wx
    return np.concatenate([lf,rf,[lx,rx,float(len(res.hand_landmarks))]])

# ── PREDICTOR CLASS ───────────────────────────────────────────────────────
class GesturePredictor:
    def __init__(self):
        self.device = torch.device('cpu')
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model not found: {MODEL_PATH}\nRun train_gesture_model.py first.")
        ck = torch.load(MODEL_PATH, map_location=self.device)
        self.model = GestureClassifier(ck['input_dim'], ck['num_classes'], ck.get('hidden1',128), ck.get('hidden2',64), ck.get('dropout',0.3))
        self.model.load_state_dict(ck['model_state']); self.model.eval()
        with open(SCALER_PATH,'rb') as f:  self.scaler  = pickle.load(f)
        with open(ENCODER_PATH,'rb') as f: self.encoder = pickle.load(f)
        self.class_names = list(self.encoder.classes_)
        print(f"[GesturePredictor] Classes: {self.class_names}")

        # MediaPipe detector (IMAGE mode — most reliable)
        opts = _mpv.HandLandmarkerOptions(
            base_options=_mpp.BaseOptions(model_asset_path=_MODEL_PATH),
            num_hands=2, min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            running_mode=_mpv.RunningMode.IMAGE)
        self._det    = _mpv.HandLandmarker.create_from_options(opts)
        self._ts     = 0

        self.history        = deque(maxlen=DEBOUNCE_FRAMES)
        self.reload_counter = 0
        self.action_cooldown= 0

    def predict(self, frame):
        result = {'gesture':None,'confidence':0.0,'action':None,'hand_count':0,'mp_result':None}
        if self.action_cooldown > 0: self.action_cooldown -= 1

        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._ts += 33
        res    = self._det.detect(mp_img)
        result['mp_result']  = res
        hand_count = len(res.hand_landmarks)
        result['hand_count'] = hand_count

        if not res.hand_landmarks:
            self.history.clear(); self.reload_counter=0; return result

        # ── RELOAD: both hands showing peace sign ─────────────────────────
        if hand_count == 2:
            feat   = _build_vector(res)
            scaled = self.scaler.transform([feat])
            tensor = torch.FloatTensor(scaled)
            with torch.no_grad():
                probs = torch.softmax(self.model(tensor),dim=1).numpy()[0]
            idx  = int(np.argmax(probs)); conf = float(probs[idx])
            name = self.class_names[idx]
            # If both hands and gesture is reload (peace sign) → RELOAD
            if 'reload' in name.lower() and self.action_cooldown == 0:
                self.action_cooldown = 45
                result['gesture']    = 'Reload gun (both hands)'
                result['confidence'] = float(conf)
                result['action']     = 'RELOAD'
                return result

        # ── TWO FISTS = MOVEMENT (geometric rule, no classifier needed) ──
        if hand_count == 2:
            # Get both wrist x positions (normalized 0-1)
            wx1 = res.hand_landmarks[0][0].x
            wx2 = res.hand_landmarks[1][0].x
            center_x = (wx1 + wx2) / 2.0

            # Check if both hands look like fists using classifier
            feat   = _build_vector(res)
            scaled = self.scaler.transform([feat])
            tensor = torch.FloatTensor(scaled)
            with torch.no_grad():
                probs = torch.softmax(self.model(tensor),dim=1).numpy()[0]
            idx  = int(np.argmax(probs)); conf = float(probs[idx])
            name = self.class_names[idx]

            if 'fist' in name.lower() or 'walking' in name.lower():
                # Use screen position to determine direction
                if center_x < 0.38:
                    result['gesture']    = '2 fists walking left'
                    result['confidence'] = 0.95
                    result['action']     = 'WALK_LEFT'
                elif center_x > 0.62:
                    result['gesture']    = '2 fists walking right'
                    result['confidence'] = 0.95
                    result['action']     = 'WALK_RIGHT'
                else:
                    result['gesture']    = '2 fists walking forward'
                    result['confidence'] = 0.95
                    result['action']     = 'WALK_FORWARD'
                return result

        # ── SINGLE HAND GESTURES ─────────────────────────────────────────
        feat   = _build_vector(res)
        scaled = self.scaler.transform([feat])
        tensor = torch.FloatTensor(scaled)
        with torch.no_grad():
            probs = torch.softmax(self.model(tensor),dim=1).numpy()[0]
        idx  = int(np.argmax(probs)); conf = float(probs[idx])
        if conf < CONFIDENCE_THRESHOLD: self.history.clear(); return result

        name = self.class_names[idx]
        result['gesture']    = name
        result['confidence'] = conf
        self.history.append(name)

        if len(self.history)==DEBOUNCE_FRAMES and len(set(self.history))==1:
            result['action'] = self._to_action(name, hand_count)
        return result

    def _to_action(self, g, hand_count=1):
        g = g.lower()

        # SHOOT — one finger point
        if 'point' in g or 'shooting' in g:
            if self.action_cooldown==0: self.action_cooldown=8; return 'SHOOT'

        # GRENADE — open palms
        elif 'palm' in g or 'grenade' in g:
            if self.action_cooldown==0: self.action_cooldown=30; return 'GRENADE'

        # COVER — X arms
        elif 'cover' in g or 'protection' in g:
            return 'COVER'

        # WALK FORWARD — two fists forward
        elif 'forward' in g:
            return 'WALK_FORWARD'

        # WALK LEFT — two fists left
        elif 'left' in g:
            return 'WALK_LEFT'

        # WALK RIGHT — two fists right
        elif 'right' in g:
            return 'WALK_RIGHT'

        else:
            self.reload_counter=0
        return None

    def draw_overlay(self, frame, result):
        if result.get('gesture'):
            col  = (0,255,0) if result.get('action') else (200,200,0)
            text = f"{result['gesture']} ({result['confidence']*100:.0f}%)"
            cv2.putText(frame, text, (10, frame.shape[0]-40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
        if result.get('action'):
            cv2.putText(frame, f"ACTION: {result['action']}", (10, frame.shape[0]-15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,100,255), 2)
        return frame

# ── TEST MODE ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing gesture predictor. Press Q to quit.")
    pred = GesturePredictor()
    cap  = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    while True:
        ret, frame = cap.read()
        if not ret: break
        frame  = cv2.flip(frame, 1)
        result = pred.predict(frame)

        # Big visible text in center of frame
        gesture = result.get("gesture") or "No hand detected"
        conf    = result.get("confidence", 0)
        action  = result.get("action") or ""

        # Dark background bar at top
        cv2.rectangle(frame, (0,0), (640, 80), (0,0,0), -1)
        cv2.putText(frame, f"Gesture: {gesture}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        cv2.putText(frame, f"Conf: {conf*100:.0f}%  Action: {action}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,200,255), 2)

        cv2.imshow("Gesture Test - Press Q to quit", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
    cap.release(); cv2.destroyAllWindows()
