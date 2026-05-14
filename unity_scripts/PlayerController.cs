using UnityEngine;
using UnityEngine.UI;
using System.Collections;

/// <summary>
/// FPS Player Controller driven by gesture bridge.
/// Attach to the Player GameObject (with CharacterController component).
/// </summary>
[RequireComponent(typeof(CharacterController))]
public class PlayerController : MonoBehaviour
{
    // ── References ────────────────────────────────────────────────────────
    [Header("References")]
    public Camera playerCamera;
    public GameObject gunObject;
    public Animator gunAnimator;
    public AudioSource audioSource;

    [Header("Audio Clips")]
    public AudioClip shootSound;
    public AudioClip reloadSound;
    public AudioClip grenadeThrowSound;
    public AudioClip emptyGunSound;
    public AudioClip hurtSound;
    public AudioClip coverSound;

    [Header("Effects")]
    public ParticleSystem muzzleFlash;
    public ParticleSystem grenadeExplosion;
    public GameObject bulletHolePrefab;
    public GameObject bloodSplatterPrefab;
    public GameObject grenadePrefab;
    public GameObject bulletTrailPrefab;
    public Transform bulletSpawn;

    [Header("Movement")]
    public float moveSpeed = 5f;
    public float headYawSens = 1.2f;
    public float headPitchSens = 0.8f;
    public float maxPitchUp = 60f;
    public float maxPitchDown = -40f;

    [Header("Combat")]
    public int maxAmmo = 30;
    public int maxGrenades = 90;
    public float shootRange = 80f;
    public int shootDamage = 25;
    public int grenadeDamage = 80;
    public float grenadeRadius = 8f;
    public float reloadTime = 2.0f;

    [Header("Health")]
    public int maxHealth = 100;

    // ── State ──────────────────────────────────────────────────────────────
    private CharacterController _cc;
    private int _health;
    private int _ammo;
    private int _grenades;
    private bool _reloading;
    private bool _inCover;
    private bool _isDead;
    private float _camYaw;
    private float _camPitch;
    private float _reloadTimer;
    private float _coverTimer = 0f;

    [Header("Cover")]
    public float coverDuration = 2.0f;

    // Camera shake
    private float _shakeIntensity;
    private float _shakeDuration;
    private Vector3 _shakeCamOffset;

    // Cover tween
    private Vector3 _coverOffset = new Vector3(0.4f, -0.3f, 0);

    void Awake()
    {
        _cc = GetComponent<CharacterController>();
        _health = maxHealth;
        _ammo = maxAmmo;
        _grenades = maxGrenades;
    }

    void Start()
    {
        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;
        if (playerCamera == null)
            playerCamera = Camera.main;
        _camYaw = transform.eulerAngles.y;
        _camPitch = 0f;
        UpdateHUD();
    }

    void Update()
    {
        if (_isDead) return;

        UpdateCoverTimer();
        HandleMovement();
        HandleCamera();
        HandleCombat();
        HandleReload();
        UpdateCameraShake();
        //UpdateGunPosition();
    }

    // ── COVER TIMER ──────────────────────────────────────────────────────
    void UpdateCoverTimer()
    {
        // Keyboard cover: holding C keeps cover active.
        // Gesture cover: one detected COVER action activates cover for coverDuration seconds.
        bool keyboardCoverHeld = Input.GetKey(KeyCode.C);

        if (keyboardCoverHeld)
        {
            _coverTimer = coverDuration;
            _inCover = true;
        }
        else if (_coverTimer > 0f)
        {
            _coverTimer -= Time.deltaTime;
            _inCover = true;
        }
        else
        {
            _coverTimer = 0f;
            _inCover = false;
        }

        if (HUDController.Instance)
            HUDController.Instance.SetCover(_inCover);
    }

    // ── MOVEMENT ──────────────────────────────────────────────────────────
    void HandleMovement()
    {
        var bridge = GestureBridge.Instance;
        Vector3 move = Vector3.zero;

        // Keyboard fallback
        float kH = Input.GetAxis("Horizontal");
        float kV = Input.GetAxis("Vertical");
        move += transform.right * kH;
        move += transform.forward * kV;

        // Gesture movement
        if (bridge != null)
        {
            if (bridge.ActionWalkForward) move += transform.forward;
            if (bridge.ActionWalkLeft) move -= transform.right;
            if (bridge.ActionWalkRight) move += transform.right;
        }

        // Cover slows movement
        float spd = _inCover ? moveSpeed * 0.3f : moveSpeed;
        move = Vector3.ClampMagnitude(move, 1f) * spd;
        move.y = -9.81f; // gravity
        _cc.Move(move * Time.deltaTime);
    }

    // ── CAMERA ────────────────────────────────────────────────────────────
    void HandleCamera()
    {
        var bridge = GestureBridge.Instance;

        // Mouse fallback
        float mX = Input.GetAxis("Mouse X") * 2f;
        float mY = Input.GetAxis("Mouse Y") * 2f;

        float yawDelta = mX;
        float pitchDelta = -mY;

        // Head pose input
        if (bridge != null)
        {
            yawDelta += bridge.HeadYaw * headYawSens * Time.deltaTime * 60f;
            pitchDelta += bridge.HeadPitch * headPitchSens * Time.deltaTime * 60f;
        }

        _camYaw += yawDelta;
        _camPitch = Mathf.Clamp(_camPitch + pitchDelta, maxPitchDown, maxPitchUp);

        transform.rotation = Quaternion.Euler(0, _camYaw, 0);
        playerCamera.transform.localRotation = Quaternion.Euler(_camPitch, 0, 0);
    }

    // ── COMBAT ────────────────────────────────────────────────────────────
    void HandleCombat()
    {
        var bridge = GestureBridge.Instance;
        string action = bridge != null ? bridge.CurrentAction : "";

        bool shootInput = Input.GetButtonDown("Fire1") || (bridge != null && bridge.ActionShoot);
        bool grenadeInput = Input.GetKeyDown(KeyCode.G) || (bridge != null && bridge.ActionGrenade);
        bool coverInput = Input.GetKey(KeyCode.C) || action == "COVER";
        bool reloadInput = Input.GetKeyDown(KeyCode.R) || (bridge != null && bridge.ActionReload);
        // Cover: holding C keeps cover active; gesture activates it for a few seconds.
        if (coverInput)
        {
            _coverTimer = coverDuration;
            _inCover = true;

            if (Input.GetKeyDown(KeyCode.C) || action == "COVER")
                PlaySound(coverSound);
        }

        // Shoot
        if (shootInput && !_reloading)
        {
            if (_ammo > 0)
            {
                DoShoot();
            }
            else
            {
                PlaySound(emptyGunSound);
            }
        }

        // Grenade
        if (grenadeInput && _grenades > 0 && !_reloading)
        {
            DoGrenade();
        }

        // Reload keyboard
        if (Input.GetKeyDown(KeyCode.R) || action == "RELOAD")
        {
            TryReload();
        }
    }

    void DoShoot()
    {
        _ammo--;
        PlaySound(shootSound);
        if (muzzleFlash) muzzleFlash.Play();
        if (gunAnimator) gunAnimator.SetTrigger("Shoot");
        ShakeCamera(0.15f, 0.12f);
        StartCoroutine(GunRecoil());
        FlashCrosshair();

        // Raycast shooting: damage is instant, bullet trail is only visual.
        Ray ray = new Ray(playerCamera.transform.position,
                          playerCamera.transform.forward);

        Vector3 trailStart = bulletSpawn != null
            ? bulletSpawn.position
            : playerCamera.transform.position + playerCamera.transform.forward * 0.7f;

        Vector3 trailEnd = playerCamera.transform.position + playerCamera.transform.forward * shootRange;

        if (Physics.Raycast(ray, out RaycastHit hit, shootRange))
        {
            trailEnd = hit.point;

            // Enemy hit
            EnemyAI enemy = hit.collider.GetComponentInParent<EnemyAI>();
            if (enemy != null)
            {
                enemy.TakeDamage(shootDamage);
                if (bloodSplatterPrefab)
                    Instantiate(bloodSplatterPrefab, hit.point,
                        Quaternion.LookRotation(hit.normal));
            }
            else if (bulletHolePrefab)
            {
                // Bullet hole on surfaces
                Instantiate(bulletHolePrefab, hit.point + hit.normal * 0.01f,
                    Quaternion.LookRotation(hit.normal));
            }
        }

        SpawnBulletTrail(trailStart, trailEnd);

        UpdateHUD();

        if (_ammo == 0) TryReload();
    }

    void SpawnBulletTrail(Vector3 start, Vector3 end)
    {
        GameObject trailObj;

        if (bulletTrailPrefab != null)
            trailObj = Instantiate(bulletTrailPrefab, start, Quaternion.identity);
        else
            trailObj = new GameObject("Runtime_BulletTrail");

        LineRenderer lr = trailObj.GetComponent<LineRenderer>();
        if (lr == null) lr = trailObj.AddComponent<LineRenderer>();

        lr.positionCount = 2;
        lr.SetPosition(0, start);
        lr.SetPosition(1, end);
        lr.useWorldSpace = true;

        // Force visible settings even if the prefab material is bad.
        lr.startWidth = 0.08f;
        lr.endWidth = 0.02f;
        lr.startColor = Color.yellow;
        lr.endColor = new Color(1f, 0.45f, 0f, 0.2f);

        if (lr.material == null)
        {
            Shader shader = Shader.Find("Sprites/Default");
            if (shader == null) shader = Shader.Find("Universal Render Pipeline/Unlit");
            if (shader != null) lr.material = new Material(shader);
        }

        Destroy(trailObj, 0.03f);
    }

    IEnumerator GunRecoil()
    {
        if (gunObject == null) yield break;

        Vector3 originalPos = gunObject.transform.localPosition;
        Vector3 recoilPos = originalPos + new Vector3(0f, -0.04f, -0.08f);

        gunObject.transform.localPosition = recoilPos;

        yield return new WaitForSeconds(0.07f);

        gunObject.transform.localPosition = originalPos;
    }

    void DoGrenade()
    {
        _grenades--;
        PlaySound(grenadeThrowSound);
        if (gunAnimator) gunAnimator.SetTrigger("Grenade");

        if (grenadePrefab)
        {
            Vector3 throwDir = playerCamera.transform.forward +
                               playerCamera.transform.up * 0.3f;
            GameObject g = Instantiate(grenadePrefab,
                playerCamera.transform.position + playerCamera.transform.forward,
                Quaternion.identity);
            Rigidbody rb = g.GetComponent<Rigidbody>();
            if (rb) rb.AddForce(throwDir.normalized * 18f, ForceMode.VelocityChange);
            StartCoroutine(ExplodeGrenade(g));
        }
        else
        {
            // Immediate explosion if no prefab
            DoGrenadeExplosion(playerCamera.transform.position +
                               playerCamera.transform.forward * 15f);
        }
        UpdateHUD();
    }

    IEnumerator ExplodeGrenade(GameObject grenade)
    {
        yield return new WaitForSeconds(2.5f);
        if (grenade)
        {
            DoGrenadeExplosion(grenade.transform.position);
            Destroy(grenade);
        }
    }

    void DoGrenadeExplosion(Vector3 pos)
    {
        if (grenadeExplosion)
        {
            var fx = Instantiate(grenadeExplosion, pos, Quaternion.identity);
            fx.Play();
            Destroy(fx.gameObject, 3f);
        }
        ShakeCamera(0.4f, 0.5f);

        // Damage enemies in radius
        Collider[] hits = Physics.OverlapSphere(pos, grenadeRadius);
        foreach (var col in hits)
        {
            EnemyAI en = col.GetComponentInParent<EnemyAI>();
            if (en != null)
            {
                float dist = Vector3.Distance(pos, en.transform.position);
                int dmg = Mathf.RoundToInt(grenadeDamage * (1f - dist / grenadeRadius));
                en.TakeDamage(Mathf.Max(dmg, 10));
            }
        }
    }

    void FlashCrosshair()
    {
        if (HUDController.Instance)
            StartCoroutine(CrosshairFlashRoutine());
    }

    IEnumerator CrosshairFlashRoutine()
    {
        ImageFlash(Color.red);
        yield return new WaitForSeconds(0.08f);
        ImageFlash(Color.white);
    }

    void ImageFlash(Color color)
    {
        if (HUDController.Instance == null) return;

        var hud = HUDController.Instance;

        if (hud.crosshairCenter) hud.crosshairCenter.color = color;
        if (hud.crosshairTop) hud.crosshairTop.color = color;
        if (hud.crosshairBottom) hud.crosshairBottom.color = color;
        if (hud.crosshairLeft) hud.crosshairLeft.color = color;
        if (hud.crosshairRight) hud.crosshairRight.color = color;
    }

    // ── RELOAD ────────────────────────────────────────────────────────────
    void TryReload()
    {
        if (_reloading || _ammo == maxAmmo) return;
        _reloading = true;
        _reloadTimer = reloadTime;
        PlaySound(reloadSound);
        if (gunAnimator) gunAnimator.SetTrigger("Reload");
        if (HUDController.Instance) HUDController.Instance.ShowReloading(true);
    }

    void HandleReload()
    {
        if (!_reloading) return;
        _reloadTimer -= Time.deltaTime;
        if (_reloadTimer <= 0)
        {
            _ammo = maxAmmo;
            _reloading = false;
            if (HUDController.Instance) HUDController.Instance.ShowReloading(false);
            UpdateHUD();
        }
    }

    // ── DAMAGE ────────────────────────────────────────────────────────────
    public void TakeDamage(int dmg)
    {
        // Strong cover protection: works for both keyboard C and gesture cover.
        var bridge = GestureBridge.Instance;
        bool coverNow = _inCover || _coverTimer > 0f || Input.GetKey(KeyCode.C) ||
                        (bridge != null && bridge.CurrentAction == "COVER");

        if (_isDead || coverNow)
        {
            _coverTimer = Mathf.Max(_coverTimer, 0.5f);
            _inCover = true;
            if (HUDController.Instance) HUDController.Instance.SetCover(true);
            return;
        }

        _health = Mathf.Max(0, _health - dmg);
        PlaySound(hurtSound);
        ShakeCamera(0.3f, 0.2f);
        if (HUDController.Instance) HUDController.Instance.ShowHitFlash();
        UpdateHUD();
        if (_health == 0) Die();
    }

    void Die()
    {
        _isDead = true;
        if (GameManager.Instance) GameManager.Instance.OnPlayerDied();
    }

    // ── CAMERA SHAKE ─────────────────────────────────────────────────────
    public void ShakeCamera(float intensity, float duration)
    {
        _shakeIntensity = intensity;
        _shakeDuration = duration;
    }

    void UpdateCameraShake()
    {
        if (_shakeDuration > 0)
        {
            _shakeDuration -= Time.deltaTime;
            _shakeCamOffset = Random.insideUnitSphere * _shakeIntensity;
            playerCamera.transform.localPosition = _shakeCamOffset;
        }
        else
        {
            playerCamera.transform.localPosition =
                Vector3.Lerp(playerCamera.transform.localPosition,
                             Vector3.zero, Time.deltaTime * 10f);
        }
    }

    // ── GUN POSITION ─────────────────────────────────────────────────────
    void UpdateGunPosition()
    {
        if (gunObject == null) return;
        Vector3 targetPos = _inCover
            ? new Vector3(0.3f, -0.25f, 0.5f)
            : new Vector3(0.18f, -0.15f, 0.4f);
        gunObject.transform.localPosition =
            Vector3.Lerp(gunObject.transform.localPosition,
                         targetPos, Time.deltaTime * 8f);
    }

    // ── HUD UPDATE ────────────────────────────────────────────────────────
    void UpdateHUD()
    {
        if (HUDController.Instance)
            HUDController.Instance.UpdateStats(_health, maxHealth,
                                               _ammo, maxAmmo,
                                               _grenades, maxGrenades);
    }

    void PlaySound(AudioClip clip)
    {
        if (clip && audioSource) audioSource.PlayOneShot(clip);
    }

    // ── PUBLIC GETTERS ────────────────────────────────────────────────────
    public bool IsDead => _isDead;
    public bool IsInCover => _inCover;
    public int Health => _health;

    Transform FindClosestEnemy()
    {
        GameObject[] enemies = GameObject.FindGameObjectsWithTag("Enemy");

        Transform closest = null;
        float minDistance = Mathf.Infinity;

        foreach (GameObject enemy in enemies)
        {
            float dist = Vector3.Distance(transform.position, enemy.transform.position);

            if (dist < minDistance)
            {
                minDistance = dist;
                closest = enemy.transform;
            }
        }

        return closest;
    }

}
