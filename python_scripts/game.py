"""
GESTUREWAR 3D — Ursina Engine
================================
Professional first-person shooter
- Real 3D world with your battlefield video as sky/background
- 3D soldiers walking toward you with weapons
- Muzzle flash, explosions, blood effects
- Professional CoD-style HUD
- Gesture + head pose controlled
- Sounds, screen shake, waves

INSTALL:
    pip install ursina

RUN:
    python game.py
"""

from ursina import *
from ursina.shaders import lit_with_shadows_shader
import cv2, numpy as np
import os, math, time, random, threading, sys

# ── PATHS ─────────────────────────────────────────────────────────────────
DATASET_ROOT = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset"
BATTLEFIELD_DIR = os.path.join(DATASET_ROOT, "battlefield")
MODELS_DIR = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset\gesture_models"

BATTLEFIELD_VIDEOS = [
    "WhatsApp Video 2026-05-04 at 5.01.05 PM.mp4",
    "WhatsApp Video 2026-05-04 at 5.01.39 PM.mp4",
    "WhatsApp Video 2026-05-04 at 5.02.03 PM.mp4",
]

# ── SETTINGS ──────────────────────────────────────────────────────────────
MAX_HEALTH   = 100
MAX_AMMO     = 30
MAX_GRENADES = 3
TOTAL_WAVES  = 3

ENEMY_CFG = {
    'basic':   {'hp':40,  'spd':2.2, 'pts':10, 'dmg':5,  'color':color.rgb(55,100,55)},
    'soldier': {'hp':80,  'spd':3.0, 'pts':25, 'dmg':10, 'color':color.rgb(55,55,120)},
    'elite':   {'hp':130, 'spd':4.0, 'pts':50, 'dmg':18, 'color':color.rgb(140,30,30)},
}

WAVES = [
    [('basic',6)],
    [('basic',4),('soldier',4)],
    [('basic',3),('soldier',3),('elite',3)],
]

SPAWN_POSITIONS = [
    Vec3(-18, 0, -40), Vec3(-10, 0, -45), Vec3(0,  0, -50),
    Vec3(10,  0, -45), Vec3(18, 0, -40),  Vec3(-14, 0, -42),
    Vec3(6,   0, -48), Vec3(-6, 0, -43),
]

# ── APP ───────────────────────────────────────────────────────────────────
app = Ursina(
    title='GestureWar',
    fullscreen=False,
    size=(1280, 720),
    vsync=True,
)
window.color = color.black

# ── SHADERS / LIGHTING ────────────────────────────────────────────────────
AmbientLight(color=color.rgba(80, 90, 80, 255))
sun = DirectionalLight(shadows=True)
sun.look_at(Vec3(1, -2, 1))


# ══════════════════════════════════════════════════════════════════════════
# CV THREAD
# ══════════════════════════════════════════════════════════════════════════
class CVThread:
    def __init__(self):
        self._result  = {'gesture':'','confidence':0,'action':None,
                         'hand_count':0,'yaw':0,'pitch':0}
        self._pending = None
        self._lock    = threading.Lock()
        self._running = True
        self._pred    = None
        self._hp      = None
        self._cap     = None
        self._init()
        threading.Thread(target=self._run, daemon=True).start()

    def _init(self):
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from gesture_predictor import GesturePredictor
            self._pred = GesturePredictor()
            print("✅ Gesture predictor loaded")
        except Exception as e:
            print(f"⚠ Gesture: {e}")
        try:
            import head_pose as hp
            self._hp = hp
            print("✅ Head pose loaded")
        except Exception as e:
            print(f"⚠ Head pose: {e}")
        self._cap = cv2.VideoCapture(0)
        if self._cap.isOpened():
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            print("✅ Webcam opened")
        else:
            print("⚠ No webcam"); self._cap = None

    def _run(self):
        while self._running:
            if not self._cap or not self._cap.isOpened():
                time.sleep(0.05); continue
            ret, frame = self._cap.read()
            if not ret: continue
            frame = cv2.flip(frame, 1)
            gr  = {'gesture':'','confidence':0,'action':None,'hand_count':0}
            ang = {'yaw':0,'pitch':0}
            if self._pred:
                try: gr = self._pred.predict(frame)
                except: pass
            if self._hp:
                try: ang = self._hp.get_head_angles(frame)
                except: pass
            with self._lock:
                self._result.update({
                    'gesture':    gr.get('gesture') or '',
                    'confidence': gr.get('confidence', 0),
                    'hand_count': gr.get('hand_count', 0),
                    'yaw':        ang.get('yaw', 0),
                    'pitch':      ang.get('pitch', 0),
                })
                a = gr.get('action')
                if a: self._pending = a; self._result['action'] = a

    def get(self):
        with self._lock:
            d = dict(self._result)
            d['action']          = self._pending
            self._pending        = None
            self._result['action'] = None
        return d

    def stop(self):
        self._running = False
        if self._cap: self._cap.release()


# ══════════════════════════════════════════════════════════════════════════
# BACKGROUND VIDEO
# ══════════════════════════════════════════════════════════════════════════
class VideoBackground:
    def __init__(self):
        self._frames  = []
        self._idx     = 0
        self._timer   = 0
        self._tex     = None
        self._entity  = None
        self._load()
        self._setup_entity()

    def _load(self):
        print("Loading battlefield videos...")
        for vname in BATTLEFIELD_VIDEOS:
            vpath = os.path.join(BATTLEFIELD_DIR, vname)
            if not os.path.exists(vpath):
                print(f"  ⚠ Not found: {vname}"); continue
            cap = cv2.VideoCapture(vpath)
            cnt = 0
            while cnt < 250:
                ret, frm = cap.read()
                if not ret: break
                if cnt % 3 == 0:
                    frm = cv2.resize(frm, (1280, 720))
                    frm = cv2.cvtColor(frm, cv2.COLOR_BGR2RGB)
                    self._frames.append(frm)
                cnt += 1
            cap.release()
        if not self._frames:
            print("  Using solid background")
            dummy = np.zeros((720, 1280, 3), dtype=np.uint8)
            dummy[:360] = [60, 80, 100]
            dummy[360:] = [40, 50, 30]
            self._frames = [dummy]
        print(f"  ✅ {len(self._frames)} frames")

    def _setup_entity(self):
        frm  = self._frames[0]
        img  = frm.flatten().tobytes()
        self._tex = Texture(frm.shape[1], frm.shape[0])
        self._tex.setRamImage(img)
        self._entity = Entity(
            model='quad',
            texture=self._tex,
            scale=(160, 90),
            position=(0, 20, -99),
            unlit=True,
            eternal=True,
        )

    def update(self):
        self._timer += 1
        if self._timer >= 2:
            self._timer = 0
            self._idx   = (self._idx + 1) % len(self._frames)
            frm = self._frames[self._idx]
            self._tex.setRamImage(frm.flatten().tobytes())


# ══════════════════════════════════════════════════════════════════════════
# SOLDIER ENTITY (3D)
# ══════════════════════════════════════════════════════════════════════════
class Soldier(Entity):
    def __init__(self, etype, spawn_pos, **kwargs):
        super().__init__(**kwargs)

        cfg         = ENEMY_CFG[etype]
        self.etype  = etype
        self.cfg    = cfg
        self.hp     = cfg['hp']
        self.max_hp = cfg['hp']
        self.spd    = cfg['spd']
        self.pts    = cfg['pts']
        self.dmg    = cfg['dmg']
        self.alive  = True
        self._flash = 0
        self._shoot_cd = random.uniform(1.5, 3.5)
        self._wobble   = random.uniform(0, math.pi*2)

        col = cfg['color']

        # ── Build soldier from Ursina primitives ─────────────────────────
        # Torso
        self.torso = Entity(parent=self, model='cube',
            color=col, scale=(0.55,0.65,0.28),
            position=(0, 1.15, 0))

        # Vest (darker layer on torso)
        vest_col = color.rgb(
            max(0, col.r*255 - 30),
            max(0, col.g*255 - 30),
            max(0, col.b*255 - 30))
        self.vest = Entity(parent=self, model='cube',
            color=vest_col, scale=(0.45, 0.55, 0.12),
            position=(0, 1.15, 0.09))

        # Pouches on vest
        for px in [-0.14, 0, 0.14]:
            Entity(parent=self, model='cube',
                color=color.rgb(30,40,25),
                scale=(0.1, 0.12, 0.08),
                position=(px, 1.0, 0.16))

        # Head
        self.head = Entity(parent=self, model='sphere',
            color=color.rgb(195,155,115),
            scale=(0.32, 0.32, 0.32),
            position=(0, 1.72, 0))

        # Helmet
        self.helmet = Entity(parent=self, model='sphere',
            color=color.rgb(
                max(0, col.r*255 - 40),
                max(0, col.g*255 - 40),
                max(0, col.b*255 - 40)),
            scale=(0.36, 0.26, 0.38),
            position=(0, 1.82, 0))

        # Goggles
        Entity(parent=self, model='cube',
            color=color.rgb(15,15,15),
            scale=(0.32, 0.07, 0.06),
            position=(0, 1.72, 0.17))

        # Left arm
        self.larm = Entity(parent=self, model='cube',
            color=col, scale=(0.18, 0.55, 0.18),
            position=(-0.37, 1.12, 0))

        # Right arm
        self.rarm = Entity(parent=self, model='cube',
            color=col, scale=(0.18, 0.55, 0.18),
            position=(0.37, 1.12, 0))

        # Left leg
        self.lleg = Entity(parent=self, model='cube',
            color=color.rgb(
                max(0, col.r*255-20),
                max(0, col.g*255-20),
                max(0, col.b*255-20)),
            scale=(0.22, 0.65, 0.22),
            position=(-0.16, 0.45, 0))

        # Right leg
        self.rleg = Entity(parent=self, model='cube',
            color=color.rgb(
                max(0, col.r*255-20),
                max(0, col.g*255-20),
                max(0, col.b*255-20)),
            scale=(0.22, 0.65, 0.22),
            position=(0.16, 0.45, 0))

        # Boots
        for bx in [-0.16, 0.16]:
            Entity(parent=self, model='cube',
                color=color.rgb(25,20,15),
                scale=(0.25, 0.15, 0.30),
                position=(bx, 0.08, 0.04))

        # Rifle (left side)
        self.gun_body = Entity(parent=self, model='cube',
            color=color.rgb(20,20,20),
            scale=(0.08, 0.12, 0.65),
            position=(-0.52, 1.18, 0))
        Entity(parent=self, model='cube',
            color=color.rgb(15,15,15),
            scale=(0.05, 0.05, 0.40),
            position=(-0.52, 1.18, -0.52))
        # Gun magazine
        Entity(parent=self, model='cube',
            color=color.rgb(30,30,30),
            scale=(0.06, 0.18, 0.08),
            position=(-0.52, 1.05, -0.08))

        # Type indicator dot on helmet
        dot_colors = {'basic':color.lime,'soldier':color.cyan,'elite':color.red}
        Entity(parent=self, model='sphere',
            color=dot_colors.get(etype, color.white),
            scale=0.07,
            position=(0.12, 1.90, 0.12))

        # Health bar (billboard — always faces camera)
        self.hp_bar_bg = Entity(parent=self, model='quad',
            color=color.rgb(80,0,0),
            scale=(0.9, 0.08),
            position=(0, 2.3, 0),
            billboard=True)
        self.hp_bar = Entity(parent=self, model='quad',
            color=color.lime,
            scale=(0.9, 0.08),
            position=(0, 2.3, 0.01),
            billboard=True)

        # Set world position
        self.position  = spawn_pos
        self.scale     = Vec3(1, 1, 1)
        self._walk_t   = 0
        self._orig_y   = spawn_pos.y

    def update_hp_bar(self):
        pct = self.hp / self.max_hp
        self.hp_bar.scale_x = 0.9 * pct
        self.hp_bar.x       = -0.45 * (1 - pct)
        self.hp_bar.color   = (color.lime   if pct > 0.5 else
                               color.yellow if pct > 0.25 else
                               color.red)

    def take_hit(self, dmg):
        self.hp -= dmg
        self._flash = 5
        self.update_hp_bar()
        # Flash white
        for e in self.children:
            if hasattr(e, 'color') and e != self.hp_bar and e != self.hp_bar_bg:
                e.color = color.white
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def do_update(self, player_pos, dt):
        if not self.alive: return

        # Face player
        dir_to = player_pos - self.position
        dir_to.y = 0
        if dir_to.length() > 0.1:
            angle = math.degrees(math.atan2(dir_to.x, dir_to.z))
            self.rotation_y = angle

        # Walk toward player
        dist = distance(self.position, player_pos)
        if dist > 2.0:
            move = dir_to.normalized() * self.spd * dt
            self.position += move

        # Walking animation (bob up/down)
        self._walk_t += dt * self.spd * 2
        self.y = self._orig_y + abs(math.sin(self._walk_t)) * 0.08

        # Arm swing
        swing = math.sin(self._walk_t) * 20
        self.larm.rotation_x =  swing
        self.rarm.rotation_x = -swing
        self.lleg.rotation_x = -swing * 0.8
        self.rleg.rotation_x =  swing * 0.8

        # Flash reset
        if self._flash > 0:
            self._flash -= 1
            if self._flash == 0:
                col = self.cfg['color']
                for e in self.children:
                    if e == self.torso: e.color = col
                    elif e == self.larm or e == self.rarm: e.color = col
                    elif e == self.lleg or e == self.rleg:
                        e.color = color.rgb(
                            max(0,col.r*255-20),
                            max(0,col.g*255-20),
                            max(0,col.b*255-20))

        # Shoot cooldown
        self._shoot_cd -= dt
        if self._shoot_cd <= 0 and dist < 25:
            self._shoot_cd = random.uniform(1.5, 3.0)
            return 'SHOOT'  # signal to game to deal damage

        return None


# ══════════════════════════════════════════════════════════════════════════
# EFFECTS
# ══════════════════════════════════════════════════════════════════════════
class MuzzleFlash(Entity):
    def __init__(self, **kwargs):
        super().__init__(
            model='sphere',
            color=color.yellow,
            scale=0,
            unlit=True,
            **kwargs)
        self._t = 0

    def trigger(self):
        self.scale  = random.uniform(0.15, 0.25)
        self.color  = color.rgb(255, random.randint(180,255), 0)
        self._t     = 0.08

    def do_update(self, dt):
        if self._t > 0:
            self._t    -= dt
            self.scale  = max(0, self._t * 3)
        else:
            self.scale = 0


class BloodParticle(Entity):
    def __init__(self, pos, **kwargs):
        super().__init__(
            model='sphere',
            color=color.rgb(180, 10, 10),
            scale=random.uniform(0.06, 0.15),
            position=pos,
            unlit=True,
            **kwargs)
        self._vx = random.uniform(-3, 3)
        self._vy = random.uniform(2, 6)
        self._vz = random.uniform(-3, 3)
        self._life = random.uniform(0.3, 0.7)

    def do_update(self, dt):
        self._vy   -= 12 * dt
        self.x     += self._vx * dt
        self.y     += self._vy * dt
        self.z     += self._vz * dt
        self._life -= dt
        if self._life <= 0:
            destroy(self)
            return True
        return False


class ExplosionEffect(Entity):
    def __init__(self, pos, **kwargs):
        super().__init__(
            model='sphere',
            color=color.orange,
            scale=0.1,
            position=pos,
            unlit=True,
            **kwargs)
        self._t     = 0
        self._max_t = 0.6
        self._max_s = 6.0

    def do_update(self, dt):
        self._t += dt
        prog = self._t / self._max_t
        if prog >= 1:
            destroy(self)
            return True
        s = self._max_s * math.sin(prog * math.pi)
        self.scale = s
        r = int(255)
        g = int(max(0, 200 * (1 - prog)))
        self.color = color.rgb(r, g, 0)
        return False


class ScreenShaker:
    def __init__(self): self._v = 0
    def shake(self, s=0.05): self._v = s
    def do_update(self, dt):
        if self._v > 0:
            self._v = max(0, self._v - dt * 0.3)
            camera.shake(self._v)


# ══════════════════════════════════════════════════════════════════════════
# GUN MODEL (first-person)
# ══════════════════════════════════════════════════════════════════════════
class FPSGun(Entity):
    def __init__(self):
        super().__init__(parent=camera.ui)
        # Gun parts positioned in screen space
        self._recoil    = 0
        self._reload_t  = 0
        self._reloading = False
        self._build()

    def _build(self):
        # Main gun body
        self.body = Entity(parent=camera, model='cube',
            color=color.rgb(25,25,25),
            scale=(0.06, 0.05, 0.38),
            position=(0.22, -0.18, 0.45),
            unlit=True)
        # Barrel
        self.barrel = Entity(parent=camera, model='cube',
            color=color.rgb(18,18,18),
            scale=(0.04, 0.03, 0.22),
            position=(0.22, -0.17, 0.28),
            unlit=True)
        # Grip
        self.grip = Entity(parent=camera, model='cube',
            color=color.rgb(22,22,22),
            scale=(0.04, 0.10, 0.05),
            position=(0.26, -0.24, 0.48),
            unlit=True)
        # Magazine
        self.mag = Entity(parent=camera, model='cube',
            color=color.rgb(35,35,35),
            scale=(0.035, 0.09, 0.06),
            position=(0.22, -0.22, 0.44),
            unlit=True)
        # Scope / rail
        self.scope = Entity(parent=camera, model='cube',
            color=color.rgb(20,20,20),
            scale=(0.025, 0.025, 0.12),
            position=(0.22, -0.145, 0.42),
            unlit=True)
        # Muzzle flash
        self.muzzle = MuzzleFlash(parent=camera,
            position=(0.22, -0.17, 0.17))
        # Fore grip
        Entity(parent=camera, model='cube',
            color=color.rgb(30,30,30),
            scale=(0.06, 0.035, 0.06),
            position=(0.22, -0.205, 0.30),
            unlit=True)

    def shoot(self):
        self._recoil = 0.03
        self.muzzle.trigger()

    def reload(self):
        self._reloading = True
        self._reload_t  = 0

    def do_update(self, dt):
        self.muzzle.do_update(dt)
        # Recoil
        if self._recoil > 0:
            self._recoil = max(0, self._recoil - dt * 0.5)
            offset = self._recoil
            for part in [self.body, self.barrel, self.grip,
                          self.mag, self.scope]:
                part.z += offset * 0.3
                part.y += offset * 0.2

        if self._reloading:
            self._reload_t += dt
            angle = math.sin(self._reload_t * 3) * 20
            for part in [self.body, self.barrel, self.grip, self.mag, self.scope]:
                part.rotation_z = angle
            if self._reload_t >= 2.0:
                self._reloading = False
                for part in [self.body, self.barrel, self.grip, self.mag, self.scope]:
                    part.rotation_z = 0


# ══════════════════════════════════════════════════════════════════════════
# HUD (Ursina UI)
# ══════════════════════════════════════════════════════════════════════════
class GameHUD:
    def __init__(self):
        # ── Health bar ────────────────────────────────────────────────────
        self.hp_bg = Entity(parent=camera.ui, model='quad',
            color=color.rgba(0,0,0,180),
            scale=(0.32,0.04), position=(-0.58,-0.43))
        self.hp_bar = Entity(parent=camera.ui, model='quad',
            color=color.lime,
            scale=(0.30,0.03), position=(-0.585,-0.43))
        self.hp_text = Text(parent=camera.ui,
            text='100', position=(-0.68,-0.44),
            scale=1.2, color=color.white)
        # Heart
        Text(parent=camera.ui, text='♥',
            position=(-0.72,-0.44), scale=1.4, color=color.red)

        # ── Ammo ──────────────────────────────────────────────────────────
        self.ammo_text = Text(parent=camera.ui,
            text=f'{MAX_AMMO}',
            position=(0.60,-0.44), scale=2.0,
            color=color.white, origin=(0,0))
        self.ammo_sep = Text(parent=camera.ui,
            text=f'/ {MAX_AMMO}',
            position=(0.70,-0.44), scale=1.2,
            color=color.gray, origin=(0,0))
        # Bullet icon
        Entity(parent=camera.ui, model='quad',
            color=color.yellow,
            scale=(0.008, 0.022),
            position=(0.565,-0.435))

        # ── Grenades ──────────────────────────────────────────────────────
        self.gren_icons = []
        for i in range(MAX_GRENADES):
            e = Entity(parent=camera.ui, model='circle',
                color=color.orange,
                scale=0.018,
                position=(-0.62 + i*0.04, -0.385))
            self.gren_icons.append(e)

        # ── Score ─────────────────────────────────────────────────────────
        self.score_bg = Entity(parent=camera.ui, model='quad',
            color=color.rgba(0,0,0,160),
            scale=(0.22,0.035), position=(0,-0.44))
        self.score_text = Text(parent=camera.ui,
            text='000000', position=(-0.08,-0.445),
            scale=1.3, color=color.yellow)

        # ── Wave ──────────────────────────────────────────────────────────
        self.wave_bg = Entity(parent=camera.ui, model='quad',
            color=color.rgba(0,0,0,160),
            scale=(0.18,0.06), position=(-0.72,0.44))
        self.wave_text = Text(parent=camera.ui,
            text='WAVE 1/3', position=(-0.80,0.44),
            scale=1.1, color=color.white)
        self.enemy_text = Text(parent=camera.ui,
            text='ENEMIES 0', position=(-0.80,0.41),
            scale=0.9, color=color.red)

        # ── Crosshair ─────────────────────────────────────────────────────
        gap = 0.016; ln = 0.022; th = 0.002
        self.ch_top    = Entity(parent=camera.ui, model='quad',
            color=color.white, scale=(th, ln), position=(0, gap+ln/2))
        self.ch_bottom = Entity(parent=camera.ui, model='quad',
            color=color.white, scale=(th, ln), position=(0, -gap-ln/2))
        self.ch_left   = Entity(parent=camera.ui, model='quad',
            color=color.white, scale=(ln, th), position=(-gap-ln/2, 0))
        self.ch_right  = Entity(parent=camera.ui, model='quad',
            color=color.white, scale=(ln, th), position=(gap+ln/2, 0))
        self.ch_dot    = Entity(parent=camera.ui, model='circle',
            color=color.white, scale=0.003)

        # ── Status ────────────────────────────────────────────────────────
        self.reload_text = Text(parent=camera.ui,
            text='', position=(-0.08,-0.35),
            scale=1.4, color=color.yellow)
        self.cover_text = Text(parent=camera.ui,
            text='', position=(-0.10,-0.32),
            scale=1.4, color=color.lime)

        # ── Gesture debug ─────────────────────────────────────────────────
        self.gesture_text = Text(parent=camera.ui,
            text='', position=(-0.85,-0.47),
            scale=0.8, color=color.rgb(200,200,0))

        # ── Hit flash ─────────────────────────────────────────────────────
        self.hit_flash = Entity(parent=camera.ui, model='quad',
            color=color.rgba(200,0,0,0),
            scale=(2,2))

        # ── Wave banner ───────────────────────────────────────────────────
        self.banner_text = Text(parent=camera.ui,
            text='', position=(-0.15, 0.1),
            scale=3.5, color=color.white)
        self.banner_bg   = Entity(parent=camera.ui, model='quad',
            color=color.rgba(0,0,0,0),
            scale=(0.55,0.12), position=(0,0.1))
        self._banner_t   = 0

        # ── Game over / Victory ───────────────────────────────────────────
        self.overlay = Entity(parent=camera.ui, model='quad',
            color=color.rgba(0,0,0,0), scale=(2,2))
        self.big_text  = Text(parent=camera.ui,
            text='', position=(-0.25,0.05), scale=5, color=color.white)
        self.sub_text  = Text(parent=camera.ui,
            text='', position=(-0.35,-0.05), scale=1.5, color=color.white)

        self._hit_alpha = 0

    def update_health(self, hp, max_hp):
        pct = hp / max_hp
        self.hp_bar.scale_x = 0.30 * pct
        self.hp_bar.x       = -0.585 - 0.15*(1-pct)
        self.hp_bar.color   = (color.lime   if pct>0.5 else
                               color.yellow if pct>0.25 else color.red)
        self.hp_text.text   = str(hp)

    def update_ammo(self, ammo):
        self.ammo_text.text = str(ammo)
        self.ammo_text.color = color.white if ammo > 5 else color.red

    def update_grenades(self, n):
        for i, ic in enumerate(self.gren_icons):
            ic.color = color.orange if i < n else color.rgba(80,40,0,100)

    def update_score(self, score):
        self.score_text.text = f'{score:06d}'

    def update_wave(self, wave, total, enemies):
        self.wave_text.text  = f'WAVE {wave}/{total}'
        self.enemy_text.text = f'ENEMIES {enemies}'

    def set_reloading(self, v):
        self.reload_text.text = 'RELOADING...' if v else ''

    def set_cover(self, v):
        self.cover_text.text = '[ IN COVER ]' if v else ''
        col = color.red if v else color.white
        for ch in [self.ch_top,self.ch_bottom,self.ch_left,self.ch_right,self.ch_dot]:
            ch.color = col

    def show_hit(self):
        self._hit_alpha = 0.45

    def set_gesture(self, g, conf):
        self.gesture_text.text = f'Gesture: {g}  {conf*100:.0f}%' if g else ''

    def show_banner(self, msg, col=color.white):
        self.banner_text.text  = msg
        self.banner_text.color = col
        self.banner_bg.color   = color.rgba(0,0,0,160)
        self._banner_t         = 3.0

    def show_end(self, title, sub, col):
        self.overlay.color = color.rgba(0,0,0,180)
        self.big_text.text  = title
        self.big_text.color = col
        self.sub_text.text  = sub
        self.sub_text.color = color.white

    def hide_end(self):
        self.overlay.color = color.rgba(0,0,0,0)
        self.big_text.text  = ''
        self.sub_text.text  = ''

    def do_update(self, dt):
        # Hit flash fade
        if self._hit_alpha > 0:
            self._hit_alpha = max(0, self._hit_alpha - dt*3)
            self.hit_flash.color = color.rgba(200,0,0,int(self._hit_alpha*255))

        # Banner fade
        if self._banner_t > 0:
            self._banner_t -= dt
            if self._banner_t < 1:
                a = int(self._banner_t*255)
                self.banner_text.color = color.rgba(255,255,255,a)
                self.banner_bg.color   = color.rgba(0,0,0,int(a*0.63))
            if self._banner_t <= 0:
                self.banner_text.text = ''
                self.banner_bg.color  = color.rgba(0,0,0,0)


# ══════════════════════════════════════════════════════════════════════════
# MAIN GAME
# ══════════════════════════════════════════════════════════════════════════
class GestureWar:
    def __init__(self):
        # CV
        self.cv = CVThread()

        # Background
        try:
            self.bg = VideoBackground()
        except Exception as e:
            print(f"BG error: {e}"); self.bg = None

        # Camera / player setup
        camera.position = Vec3(0, 1.7, 0)
        camera.fov      = 70
        self._cam_yaw   = 0
        self._cam_pitch = 0

        # Ground
        self.ground = Entity(
            model='plane', scale=(200,1,200),
            color=color.rgb(45,55,35),
            texture='white_cube',
            texture_scale=(40,40),
            collider='box')

        # Walls (boundaries)
        for pos, scale in [
            (Vec3(0,5,-60),  Vec3(120,10,1)),
            (Vec3(0,5,25),   Vec3(120,10,1)),
            (Vec3(-60,5,0),  Vec3(1,10,120)),
            (Vec3(60,5,0),   Vec3(1,10,120)),
        ]:
            Entity(model='cube', color=color.rgba(0,0,0,0),
                   position=pos, scale=scale, collider='box')

        # Cover objects (boxes, walls)
        self._spawn_cover()

        # Fog for atmosphere
        scene.fog_color  = color.rgb(40,50,35)
        scene.fog_density = 0.018

        # Gun
        self.gun = FPSGun()

        # HUD
        self.hud = GameHUD()

        # Shaker
        self.shaker = ScreenShaker()

        # Game state
        self._health    = MAX_HEALTH
        self._ammo      = MAX_AMMO
        self._grenades  = MAX_GRENADES
        self._score     = 0
        self._wave      = 0
        self._enemies   = []
        self._blood     = []
        self._explosions= []
        self._in_cover  = False
        self._reloading = False
        self._reload_t  = 0
        self._state     = 'playing'
        self._state_t   = 0
        self._wave_cd   = 0
        self._enemies_left = 0

        # Start first wave
        invoke(self._start_next_wave, delay=1.5)

        # Update HUD
        self._refresh_hud()

        print("="*50)
        print("  GestureWar — Running!")
        print("  WASD/arrows = move (keyboard fallback)")
        print("  Mouse = aim  |  LMB = shoot")
        print("  G=grenade  R=reload  C=cover  ESC=quit")
        print("="*50)

    def _spawn_cover(self):
        """Spawn cover objects around the battlefield."""
        cover_positions = [
            Vec3(-8, 0.5, -15), Vec3(8, 0.5, -15),
            Vec3(-5, 0.5, -25), Vec3(5, 0.5, -25),
            Vec3(0,  0.5, -20), Vec3(-12,0.5,-20),
            Vec3(12, 0.5, -20),
        ]
        for pos in cover_positions:
            Entity(model='cube',
                color=color.rgb(80,70,50),
                scale=Vec3(random.uniform(1.5,3), random.uniform(0.8,1.8), 1.2),
                position=pos,
                texture='white_cube',
                collider='box')

    def _start_next_wave(self):
        self._wave += 1
        if self._wave > TOTAL_WAVES:
            self._victory(); return

        self.hud.show_banner(f'WAVE {self._wave}', color.yellow)
        invoke(self._spawn_wave, delay=2.0)

    def _spawn_wave(self):
        cfg = WAVES[min(self._wave-1, len(WAVES)-1)]
        positions = list(SPAWN_POSITIONS)
        random.shuffle(positions)
        pi = 0
        for etype, count in cfg:
            for _ in range(count):
                pos = positions[pi % len(positions)]
                pos = Vec3(pos.x + random.uniform(-2,2), 0, pos.z + random.uniform(-2,2))
                s = Soldier(etype, pos)
                self._enemies.append(s)
                pi += 1
        self._enemies_left = len(self._enemies)
        self._refresh_hud()

    def _victory(self):
        self._state = 'victory'
        self.hud.show_end('MISSION COMPLETE',
            f'Final Score: {self._score:06d}  |  Press R to restart',
            color.yellow)

    def _game_over(self):
        self._state = 'game_over'
        self.hud.show_end('YOU DIED',
            f'Score: {self._score:06d}  |  Press R to restart',
            color.red)

    def _refresh_hud(self):
        self.hud.update_health(self._health, MAX_HEALTH)
        self.hud.update_ammo(self._ammo)
        self.hud.update_grenades(self._grenades)
        self.hud.update_score(self._score)
        self.hud.update_wave(self._wave, TOTAL_WAVES,
            len([e for e in self._enemies if e.alive]))

    def shoot(self):
        if self._ammo <= 0 or self._in_cover or self._reloading:
            return
        self._ammo -= 1
        self.gun.shoot()
        self.shaker.shake(0.04)

        # Raycast — hit enemy in crosshair
        ray = raycast(camera.world_position,
                      camera.forward, distance=60,
                      ignore=[camera])
        if ray.hit and ray.entity:
            # Find soldier parent
            en = ray.entity
            while en.parent and not isinstance(en, Soldier):
                en = en.parent
            if isinstance(en, Soldier) and en.alive:
                dmg = random.randint(18, 30)
                killed = en.take_hit(dmg)
                # Blood
                for _ in range(8):
                    self._blood.append(BloodParticle(ray.world_point))
                if killed:
                    self._score += en.pts
                    self.shaker.shake(0.06)
                    invoke(lambda e=en: self._remove_enemy(e), delay=0.5)

        self._refresh_hud()
        if self._ammo == 0:
            self._try_reload()

    def _remove_enemy(self, en):
        if en in self._enemies:
            self._enemies.remove(en)
        destroy(en)
        self._enemies_left = len([e for e in self._enemies if e.alive])
        self._refresh_hud()
        if self._enemies_left == 0 and self._state == 'playing':
            self._score += 200 * self._wave
            self.hud.show_banner(f'WAVE {self._wave} CLEAR!  +{200*self._wave}',
                                 color.lime)
            invoke(self._start_next_wave, delay=3.5)

    def grenade(self):
        if self._grenades <= 0 or self._reloading: return
        self._grenades -= 1
        self.shaker.shake(0.15)
        # Explosion ahead
        pos = camera.world_position + camera.forward * 18
        pos.y = 0.5
        ex = ExplosionEffect(pos)
        self._explosions.append(ex)
        # Damage enemies in radius
        for en in self._enemies:
            if not en.alive: continue
            d = distance(pos, en.position)
            if d < 8:
                dmg = int(80 * (1 - d/8))
                killed = en.take_hit(max(dmg,10))
                if killed:
                    self._score += en.pts
                    invoke(lambda e=en: self._remove_enemy(e), delay=0.3)
        self._refresh_hud()

    def _try_reload(self):
        if self._reloading or self._ammo == MAX_AMMO: return
        self._reloading = True
        self._reload_t  = 0
        self.gun.reload()
        self.hud.set_reloading(True)

    def update(self):
        dt = time.dt

        if self._state == 'game_over' or self._state == 'victory':
            if held_keys['r']:
                self._restart()
            return

        cv = self.cv.get()
        action  = cv.get('action')
        gesture = cv.get('gesture') or ''

        # ── Input ──────────────────────────────────────────────────────────
        # Keyboard fallback
        move = Vec3(0,0,0)
        speed = 6 if not self._in_cover else 2
        if held_keys['w'] or held_keys['arrow_up']:    move += camera.forward * speed * dt
        if held_keys['s'] or held_keys['arrow_down']:  move -= camera.forward * speed * dt
        if held_keys['a'] or held_keys['arrow_left']:  move -= camera.right   * speed * dt
        if held_keys['d'] or held_keys['arrow_right']: move += camera.right   * speed * dt
        move.y = 0
        camera.position += move

        # Mouse look
        if mouse.locked:
            self._cam_yaw   += mouse.velocity[0] * 40
            self._cam_pitch  = clamp(self._cam_pitch - mouse.velocity[1]*40, -50, 60)

        # Head pose
        yaw   = cv.get('yaw', 0)
        pitch = cv.get('pitch', 0)
        self._cam_yaw   += yaw   * 0.8 * dt * 60
        self._cam_pitch  = clamp(self._cam_pitch + pitch*0.5*dt*60, -50, 60)

        camera.rotation = Vec3(self._cam_pitch, self._cam_yaw, 0)

        # Gesture actions
        if action == 'SHOOT':        self.shoot()
        elif action == 'GRENADE':    self.grenade()
        elif action == 'RELOAD':     self._try_reload()
        elif action == 'COVER':      self._toggle_cover()
        elif action == 'WALK_FORWARD':
            camera.position += camera.forward * speed * dt * 0.6
        elif action == 'WALK_LEFT':
            camera.position -= camera.right * speed * dt * 0.6
        elif action == 'WALK_RIGHT':
            camera.position += camera.right * speed * dt * 0.6

        if 'cover' not in gesture.lower() and 'protection' not in gesture.lower():
            if self._in_cover:
                self._in_cover = False
                self.hud.set_cover(False)

        # Keyboard shoot
        if held_keys['left mouse'] or held_keys['space']:
            self.shoot()
        if held_keys['g']:  self.grenade()
        if held_keys['r']:  self._try_reload()
        if held_keys['c']:  self._toggle_cover()

        # ── Reload timer ───────────────────────────────────────────────────
        if self._reloading:
            self._reload_t += dt
            if self._reload_t >= 2.0:
                self._ammo      = MAX_AMMO
                self._reloading = False
                self.hud.set_reloading(False)
                self._refresh_hud()

        # ── Update enemies ─────────────────────────────────────────────────
        for en in list(self._enemies):
            if not en.alive: continue
            result = en.do_update(camera.world_position, dt)
            if result == 'SHOOT' and not self._in_cover:
                dmg = en.dmg
                self._health = max(0, self._health - dmg)
                self.hud.show_hit()
                self.shaker.shake(0.06)
                self._refresh_hud()
                if self._health <= 0:
                    self._game_over(); return
            # Reached player
            d = distance(en.position, camera.world_position)
            if d < 1.8 and not self._in_cover:
                self._health = max(0, self._health - en.dmg*2)
                en.alive = False
                invoke(lambda e=en: self._remove_enemy(e), delay=0.1)
                self.hud.show_hit()
                self.shaker.shake(0.12)
                self._refresh_hud()
                if self._health <= 0:
                    self._game_over(); return

        # ── Update effects ─────────────────────────────────────────────────
        self.gun.do_update(dt)
        self.shaker.do_update(dt)
        self.hud.do_update(dt)
        if self.bg: self.bg.update()

        # Blood
        for b in list(self._blood):
            if b.do_update(dt):
                self._blood.remove(b)

        # Explosions
        for ex in list(self._explosions):
            if ex.do_update(dt):
                self._explosions.remove(ex)

        # HUD gesture
        self.hud.set_gesture(cv.get('gesture'), cv.get('confidence',0))

        # Keep player on ground roughly
        camera.y = lerp(camera.y, 1.7, dt*10)

    def _toggle_cover(self):
        self._in_cover = not self._in_cover
        self.hud.set_cover(self._in_cover)

    def _restart(self):
        for en in self._enemies:
            destroy(en)
        self._enemies.clear()
        for b in self._blood:
            destroy(b)
        self._blood.clear()
        for ex in self._explosions:
            destroy(ex)
        self._explosions.clear()
        self._health    = MAX_HEALTH
        self._ammo      = MAX_AMMO
        self._grenades  = MAX_GRENADES
        self._score     = 0
        self._wave      = 0
        self._in_cover  = False
        self._reloading = False
        self._state     = 'playing'
        self.hud.hide_end()
        self.hud.set_reloading(False)
        self.hud.set_cover(False)
        self._refresh_hud()
        invoke(self._start_next_wave, delay=1.5)


# ── INIT ──────────────────────────────────────────────────────────────────
game = GestureWar()
mouse.locked = True

def update():
    game.update()

def input(key):
    if key == 'escape':
        mouse.locked = not mouse.locked

app.run()
