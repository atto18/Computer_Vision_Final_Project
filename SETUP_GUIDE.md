# GestureWar — Unity Setup Guide
## Complete step-by-step instructions

---

## STEP 1 — Create the Unity Project

1. Open Unity Hub
2. Click **New Project**
3. Select **3D Core** template
4. Name it: `GestureWar`
5. Click **Create Project**

---

## STEP 2 — Install Required Packages

In Unity, go to **Window → Package Manager**:

Install these packages:
- **TextMeshPro** (built-in, just click Install)
- **Cinemachine** (for smooth camera — search and install)
- **AI Navigation** (for enemy pathfinding — search NavMesh and install)

---

## STEP 3 — Get Free Assets (IMPORTANT — makes it look like CoD)

Go to the **Unity Asset Store** (Window → Asset Store) and download these FREE assets:

1. **"Military Soldier"** — search "military soldier free" — free animated soldier model
2. **"FPS Weapon Pack"** — search "fps weapon free" — gun models with animations  
3. **"Urban City Environment"** or **"Military Base"** — free environment
4. **"Explosion effects"** — search "explosion particle free"
5. **"Blood splatter"** — search "blood particle free"

Alternative: search **"Synty Studios POLYGON"** — they have free military packs.

---

## STEP 4 — Import the Scripts

Copy the entire `Assets/Scripts/` folder into your Unity project's `Assets/` folder.

Scripts to add:
- `Bridge/GestureBridge.cs`
- `Player/PlayerController.cs`
- `Enemy/EnemyAI.cs`
- `Game/GameManager.cs`
- `Game/Grenade.cs`
- `UI/HUDController.cs`

---

## STEP 5 — Build the Scene

### 5.1 — Environment
1. Import your environment asset
2. Drag a military/urban scene into the Hierarchy
3. Make sure it has a **NavMesh** — go to **Window → AI → Navigation**, select all ground objects, click **Bake**

### 5.2 — Player Setup
1. Create empty GameObject, name it `Player`
2. Tag it as `Player` (Inspector → Tag → Add Tag → Player)
3. Add components:
   - `CharacterController`
   - `PlayerController` script
   - `AudioSource`
4. Create a child Camera object under Player
   - Name it `PlayerCamera`
   - Position: (0, 1.7, 0)
5. Drag gun model as child of Camera
   - Position: (0.18, -0.15, 0.4)
   - Add `Animator` component
   - Assign gun animations (shoot, reload, grenade)
6. In PlayerController Inspector, wire up:
   - Player Camera → your camera
   - Gun Object → your gun child
   - Audio clips → your sound files

### 5.3 — Gesture Bridge
1. Create empty GameObject, name it `GestureBridge`
2. Add `GestureBridge` script component
3. Port: 5065 (default)

### 5.4 — Game Manager
1. Create empty GameObject, name it `GameManager`
2. Add `GameManager` script
3. Add `AudioSource` component
4. In Inspector:
   - Assign `basicEnemyPrefab`, `soldierEnemyPrefab`, `eliteEnemyPrefab`
   - Create 6-8 empty GameObjects spread around the scene edges — these are spawn points
   - Assign them to `spawnPoints` array
   - Assign audio clips (wave start, wave clear, victory, game over, combat music)

### 5.5 — Enemy Prefabs
1. Import your soldier model
2. Create a Prefab for each type (Basic, Soldier, Elite)
3. Each prefab needs:
   - `NavMeshAgent` component (speed varies by type)
   - `Animator` component with walk, shoot, hit, die animations
   - `EnemyAI` script
   - `AudioSource`
   - Capsule Collider
   - Set enemy type in EnemyAI Inspector

### 5.6 — HUD Canvas
1. Create **UI → Canvas** (set to Screen Space - Overlay)
2. Add these UI elements:
   - **Health bar**: UI → Slider (bottom left)
   - **Ammo text**: UI → TextMeshPro (bottom right)
   - **Score text**: UI → TextMeshPro (top center)
   - **Wave text**: UI → TextMeshPro (top left)
   - **Crosshair**: 4 small white UI Images in cross pattern (center)
   - **Hit flash**: Full screen red Image with alpha 0
   - **Wave banner**: Large centered text
   - **Reload text**: Center screen "RELOADING..."
   - **Cover text**: Center screen "IN COVER"
   - **Game Over panel**: Full screen with score text
3. Add `HUDController` script to the Canvas
4. Wire up ALL UI references in the Inspector

### 5.7 — Lighting & Post Processing
1. **Window → Rendering → Lighting** → Generate lighting
2. Add **Post Processing** package (Package Manager)
3. Add Post Processing Volume to camera:
   - Bloom (intensity 0.5)
   - Color Grading (slightly desaturated, contrast +10)
   - Vignette (intensity 0.3)
   - Motion Blur (shutter 0.15)

---

## STEP 6 — Run the Python Bridge

While Unity game is running, open a terminal and run:

```
python gesture_bridge.py
```

This sends your gesture predictions to Unity via UDP.

---

## STEP 7 — Play

1. Press **Play** in Unity
2. Run `python gesture_bridge.py` in terminal
3. Show your hand gestures — they control the game in real time

---

## CONTROLS

| Gesture | Action |
|---|---|
| Point finger | Shoot |
| Open palms | Grenade |
| Both hands peace sign | Reload |
| X arms (Wakanda) | Cover |
| Two fists left/right | Move |
| Turn head | Aim |
| SPACE (keyboard) | Shoot fallback |
| G (keyboard) | Grenade fallback |
| R (keyboard) | Reload fallback |
| ESC | Quit |

---

## TROUBLESHOOTING

**Gestures not working:**
→ Make sure `gesture_bridge.py` is running
→ Check UDP port 5065 is not blocked by firewall
→ In GestureBridge Inspector, confirm port = 5065

**Enemies not moving:**
→ Make sure NavMesh is baked (Window → AI → Navigation → Bake)
→ NavMeshAgent needs a baked NavMesh to walk on

**No sounds:**
→ Assign AudioClip assets in PlayerController and GameManager Inspector

**Low FPS:**
→ Reduce shadow distance in Project Settings → Quality
→ Lower post processing effects
