using UnityEngine;
using System.Collections;
using System.Collections.Generic;

/// <summary>
/// GameManager — wave spawning, score, game state.
/// Place on an empty GameObject in the scene.
/// Assign spawn points in the Inspector.
/// </summary>
public class GameManager : MonoBehaviour
{
    public static GameManager Instance { get; private set; }

    [Header("Wave Settings")]
    public int   totalWaves      = 3;
    public float timeBetweenWaves = 3f;

    [Header("Enemy Prefabs")]
    public GameObject basicEnemyPrefab;
    public GameObject soldierEnemyPrefab;
    public GameObject eliteEnemyPrefab;

    [Header("Spawn Points")]
    public Transform[] spawnPoints;

    [Header("Audio")]
    public AudioClip waveStartSound;
    public AudioClip waveClearSound;
    public AudioClip victorySound;
    public AudioClip gameOverSound;
    public AudioSource musicSource;
    public AudioClip   combatMusic;

    // ── State ──────────────────────────────────────────────────────────────
    private int   _score;
    private int   _currentWave;
    private int   _enemiesAlive;
    private bool  _gameOver;
    private bool  _victory;
    private List<GameObject> _activeEnemies = new List<GameObject>();

    // Wave configs: (type, count) pairs
    private readonly (EnemyAI.EnemyType type, int count)[][] _waveConfigs =
    {
        new[] { (EnemyAI.EnemyType.Basic, 6) },
        new[] { (EnemyAI.EnemyType.Basic, 4), (EnemyAI.EnemyType.Soldier, 4) },
        new[] { (EnemyAI.EnemyType.Basic, 3), (EnemyAI.EnemyType.Soldier, 3),
                (EnemyAI.EnemyType.Elite, 3) },
    };

    void Awake()
    {
        if (Instance != null && Instance != this) { Destroy(gameObject); return; }
        Instance = this;
    }

    void Start()
    {
        _currentWave = 0;
        _score       = 0;
        UpdateHUD();

        if (musicSource && combatMusic)
        {
            musicSource.clip   = combatMusic;
            musicSource.loop   = true;
            musicSource.volume = 0.4f;
            musicSource.Play();
        }

        StartCoroutine(StartNextWave());
    }

    IEnumerator StartNextWave()
    {
        _currentWave++;
        if (_currentWave > totalWaves)
        {
            Victory(); yield break;
        }

        if (HUDController.Instance)
            HUDController.Instance.ShowWaveBanner($"WAVE {_currentWave}");

        PlaySound(waveStartSound);
        yield return new WaitForSeconds(timeBetweenWaves);

        SpawnWave(_currentWave - 1);
    }

    void SpawnWave(int waveIndex)
    {
        var config = _waveConfigs[Mathf.Min(waveIndex, _waveConfigs.Length - 1)];
        _activeEnemies.Clear();
        _enemiesAlive = 0;

        int spawnIdx = 0;
        foreach (var (type, count) in config)
        {
            for (int i = 0; i < count; i++)
            {
                Transform sp = spawnPoints[spawnIdx % spawnPoints.Length];
                spawnIdx++;

                // Offset so enemies don't stack
                Vector3 pos = sp.position + new Vector3(
                    Random.Range(-3f, 3f), 0, Random.Range(-3f, 3f));

                GameObject prefab = type switch
                {
                    EnemyAI.EnemyType.Soldier => soldierEnemyPrefab,
                    EnemyAI.EnemyType.Elite   => eliteEnemyPrefab,
                    _                          => basicEnemyPrefab,
                };

                if (prefab == null) continue;

                GameObject en = Instantiate(prefab, pos, sp.rotation);
                EnemyAI    ai = en.GetComponent<EnemyAI>();
                if (ai) ai.enemyType = type;

                _activeEnemies.Add(en);
                _enemiesAlive++;
            }
        }

        UpdateHUD();
        Debug.Log($"[GameManager] Wave {_currentWave} started — {_enemiesAlive} enemies");
    }

    public void AddScore(int pts)
    {
        _score += pts;
        _enemiesAlive = Mathf.Max(0, _enemiesAlive - 1);
        UpdateHUD();

        if (_enemiesAlive <= 0 && !_gameOver && !_victory)
        {
            StartCoroutine(OnWaveClear());
        }
    }

    IEnumerator OnWaveClear()
    {
        PlaySound(waveClearSound);
        _score += 200 * _currentWave;
        UpdateHUD();

        if (HUDController.Instance)
            HUDController.Instance.ShowWaveBanner($"WAVE {_currentWave} CLEAR!\n+{200*_currentWave} BONUS");

        yield return new WaitForSeconds(3f);
        StartCoroutine(StartNextWave());
    }

    public void OnPlayerDied()
    {
        _gameOver = true;
        PlaySound(gameOverSound);
        if (musicSource) musicSource.Stop();
        if (HUDController.Instance)
            HUDController.Instance.ShowGameOver(_score);
    }

    void Victory()
    {
        _victory = true;
        PlaySound(victorySound);
        if (musicSource) musicSource.Stop();
        if (HUDController.Instance)
            HUDController.Instance.ShowVictory(_score);
    }

    void UpdateHUD()
    {
        if (HUDController.Instance)
            HUDController.Instance.UpdateWave(_currentWave, totalWaves,
                                               _enemiesAlive, _score);
    }

    void PlaySound(AudioClip clip)
    {
        if (clip) AudioSource.PlayClipAtPoint(clip, Camera.main.transform.position);
    }

    public int Score       => _score;
    public int CurrentWave => _currentWave;
    public int EnemiesLeft => _enemiesAlive;
}
