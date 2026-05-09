using UnityEngine;
using UnityEngine.AI;
using System.Collections;

/// <summary>
/// Enemy AI — walks toward player, shoots, takes damage, dies.
/// Requires NavMeshAgent component.
/// Set enemy type in Inspector.
///
/// This version keeps the visible enemy bullet trail,
/// but damage is applied directly to the PlayerController when the enemy shoots.
/// This is better for the demo because the bullet visual does not need perfect collision.
/// </summary>
[RequireComponent(typeof(NavMeshAgent))]
[RequireComponent(typeof(Animator))]
public class EnemyAI : MonoBehaviour
{
    public enum EnemyType { Basic, Soldier, Elite }

    [Header("Type")]
    public EnemyType enemyType = EnemyType.Basic;

    [Header("Stats")]
    public int   maxHealth      = 60;
    public float moveSpeed      = 2.5f;
    public int   damage         = 8;
    public float attackRange    = 20f;
    public float shootInterval  = 2.0f;
    public int   scoreValue     = 10;

    [Header("Effects")]
    public ParticleSystem hitEffect;
    public ParticleSystem deathEffect;
    public AudioClip      shootSound;
    public AudioClip      hurtSound;
    public AudioClip      deathSound;

    [Header("Enemy Shooting Visuals")]
    public GameObject muzzlePoint;
    public GameObject enemyBulletTrailPrefab;
    public float bulletTrailDuration = 0.06f;

    // ── State ──────────────────────────────────────────────────────────────
    private int          _health;
    private NavMeshAgent _agent;
    private Animator     _anim;
    private AudioSource  _audio;
    private Transform    _player;
    private PlayerController _playerController;
    private bool         _isDead;
    private float        _shootTimer;
    private bool         _isShooting;

    static readonly int ANIM_WALK    = Animator.StringToHash("Walk");
    static readonly int ANIM_SHOOT   = Animator.StringToHash("Shoot");
    static readonly int ANIM_HIT     = Animator.StringToHash("Hit");
    static readonly int ANIM_DIE     = Animator.StringToHash("Die");
    static readonly int ANIM_SPEED   = Animator.StringToHash("Speed");

    void Awake()
    {
        _agent = GetComponent<NavMeshAgent>();
        _anim  = GetComponent<Animator>();
        _audio = GetComponent<AudioSource>();
        if (_audio == null) _audio = gameObject.AddComponent<AudioSource>();
        _health = maxHealth;

        // Apply type stats
        switch (enemyType)
        {
            case EnemyType.Soldier:
                maxHealth     = 100; _health = 100;
                moveSpeed     = 3.2f;
                damage        = 12;
                shootInterval = 1.5f;
                scoreValue    = 25;
                break;
            case EnemyType.Elite:
                maxHealth     = 160; _health = 160;
                moveSpeed     = 4.0f;
                damage        = 18;
                shootInterval = 1.0f;
                scoreValue    = 50;
                break;
        }

        _agent.speed = moveSpeed;
        _agent.stoppingDistance = 1.5f;
        _shootTimer = Random.Range(0f, shootInterval);
    }

    void Start()
    {
        // Find player
        var playerObj = GameObject.FindGameObjectWithTag("Player");
        if (playerObj)
        {
            _player = playerObj.transform;
            _playerController = playerObj.GetComponent<PlayerController>();
            if (_playerController == null)
                _playerController = playerObj.GetComponentInChildren<PlayerController>();
        }
    }

    void Update()
    {
        if (_isDead || _player == null) return;

        float dist = Vector3.Distance(transform.position, _player.position);

        // Always walk toward player
        if (_agent.enabled)
            _agent.SetDestination(_player.position);

        // Animation speed
        if (_anim)
        {
            _anim.SetFloat(ANIM_SPEED, _agent.velocity.magnitude / moveSpeed);
            _anim.SetBool(ANIM_WALK, _agent.velocity.magnitude > 0.1f);
        }

        // Face player
        Vector3 dir = (_player.position - transform.position).normalized;
        dir.y = 0;
        if (dir != Vector3.zero)
        {
            transform.rotation = Quaternion.Slerp(
                transform.rotation,
                Quaternion.LookRotation(dir),
                Time.deltaTime * 8f);
        }

        // Shoot when in range
        if (dist <= attackRange && !_isShooting)
        {
            _shootTimer -= Time.deltaTime;
            if (_shootTimer <= 0)
            {
                _shootTimer = shootInterval + Random.Range(-0.3f, 0.3f);
                StartCoroutine(DoShoot());
            }
        }
    }

    IEnumerator DoShoot()
    {
        if (_isDead) yield break;

        _isShooting = true;

        if (_anim) _anim.SetTrigger(ANIM_SHOOT);
        if (shootSound && _audio) _audio.PlayOneShot(shootSound, 0.5f);

        yield return new WaitForSeconds(0.3f);

        if (_isDead || _player == null)
        {
            _isShooting = false;
            yield break;
        }

        Vector3 shootOrigin = muzzlePoint != null
            ? muzzlePoint.transform.position
            : transform.position + Vector3.up * 1.4f;

        Vector3 targetPos = _player.position + Vector3.up * 1.2f;
        Vector3 shootDir = (targetPos - shootOrigin).normalized;

        // Small random spread so enemies do not look perfectly robotic.
        shootDir += new Vector3(
            Random.Range(-0.03f, 0.03f),
            Random.Range(-0.03f, 0.03f),
            Random.Range(-0.03f, 0.03f));
        shootDir.Normalize();

        Vector3 trailEnd = targetPos;

        // Visual ray only: lets the bullet trail stop on walls if there is an obstacle.
        if (Physics.Raycast(shootOrigin, shootDir, out RaycastHit hit, attackRange))
        {
            trailEnd = hit.point;
        }
        else
        {
            trailEnd = shootOrigin + shootDir * attackRange;
        }

        // Direct demo-friendly damage: if enemy shoots while player is in range, player takes damage.
        // PlayerController itself already ignores damage while cover is active.
        if (_playerController != null && !_playerController.IsInCover)
        {
            _playerController.TakeDamage(damage);
        }

        CreateBulletTrail(shootOrigin, trailEnd);

        Debug.DrawLine(shootOrigin, trailEnd, Color.red, 0.2f);
        _isShooting = false;
    }

    void CreateBulletTrail(Vector3 start, Vector3 end)
    {
        if (enemyBulletTrailPrefab == null) return;

        GameObject trail = Instantiate(enemyBulletTrailPrefab, start, Quaternion.identity);
        LineRenderer lr = trail.GetComponent<LineRenderer>();

        if (lr != null)
        {
            lr.positionCount = 2;
            lr.useWorldSpace = true;
            lr.startWidth = 0.03f;
            lr.endWidth = 0.01f;
            lr.SetPosition(0, start);
            lr.SetPosition(1, end);
        }

        Destroy(trail, bulletTrailDuration);
    }

    public void TakeDamage(int dmg)
    {
        if (_isDead) return;
        _health -= dmg;

        if (hitEffect) hitEffect.Play();
        if (hurtSound && _audio) _audio.PlayOneShot(hurtSound, 0.6f);
        if (_anim && _health > 0) _anim.SetTrigger(ANIM_HIT);

        // Flash red
        StartCoroutine(HitFlash());

        if (_health <= 0) Die();
    }

    IEnumerator HitFlash()
    {
        var renderers = GetComponentsInChildren<Renderer>();
        foreach (var r in renderers)
            foreach (var m in r.materials)
                m.color = Color.red;

        yield return new WaitForSeconds(0.08f);

        foreach (var r in renderers)
            foreach (var m in r.materials)
                m.color = Color.white;
    }

    void Die()
    {
        _isDead = true;
        if (_agent) _agent.enabled = false;

        if (_anim) _anim.SetTrigger(ANIM_DIE);
        if (deathEffect) deathEffect.Play();
        if (deathSound && _audio) _audio.PlayOneShot(deathSound);

        // Add score
        if (GameManager.Instance) GameManager.Instance.AddScore(scoreValue);

        // Ragdoll if rigidbodies exist on children
        EnableRagdoll();

        Destroy(gameObject, 4f);
    }

    void EnableRagdoll()
    {
        var rbs = GetComponentsInChildren<Rigidbody>();
        foreach (var rb in rbs)
        {
            rb.isKinematic = false;
            rb.AddForce(
                (transform.forward * -2f + Vector3.up * 1f) * 3f,
                ForceMode.Impulse);
        }

        var col = GetComponent<Collider>();
        if (col) col.enabled = false;
    }

    public bool IsDead => _isDead;
    public float HealthPercent => (float)_health / maxHealth;
}
