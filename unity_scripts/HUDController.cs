using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Collections;

/// <summary>
/// HUD Controller — manages all on-screen UI.
/// Attach to a Canvas GameObject.
/// Wire up all UI references in the Inspector.
/// </summary>
public class HUDController : MonoBehaviour
{
    public static HUDController Instance { get; private set; }

    [Header("Health")]
    public Slider     healthBar;
    public TextMeshProUGUI healthText;
    public Image      healthFill;
    public Color      healthColorHigh  = new Color(0.0f, 0.85f, 0.3f);
    public Color      healthColorMid   = new Color(1.0f, 0.85f, 0.0f);
    public Color      healthColorLow   = new Color(0.9f, 0.15f, 0.1f);

    [Header("Ammo")]
    public TextMeshProUGUI ammoText;
    public TextMeshProUGUI ammoMaxText;
    public TextMeshProUGUI grenadeText;

    [Header("Score & Wave")]
    public TextMeshProUGUI scoreText;
    public TextMeshProUGUI waveText;
    public TextMeshProUGUI enemiesLeftText;

    [Header("Gesture Debug")]
    public TextMeshProUGUI gestureText;
    public TextMeshProUGUI actionText;

    [Header("Status")]
    public GameObject reloadingPanel;
    public GameObject coverPanel;
    public TextMeshProUGUI reloadingText;

    [Header("Crosshair")]
    public Image crosshairCenter;
    public Image crosshairTop;
    public Image crosshairBottom;
    public Image crosshairLeft;
    public Image crosshairRight;

    [Header("Hit Flash")]
    public Image hitFlashImage;

    [Header("Wave Banner")]
    public TextMeshProUGUI waveBannerText;
    public CanvasGroup     waveBannerGroup;

    [Header("Game Over / Victory")]
    public GameObject      gameOverPanel;
    public TextMeshProUGUI gameOverScoreText;
    public GameObject      victoryPanel;
    public TextMeshProUGUI victoryScoreText;

    [Header("Minimap")]
    public RawImage minimapImage;

    void Awake()
    {
        if (Instance != null && Instance != this) { Destroy(gameObject); return; }
        Instance = this;
    }

    void Start()
    {
        if (hitFlashImage)   hitFlashImage.color   = new Color(1,0,0,0);
        if (waveBannerGroup) waveBannerGroup.alpha  = 0;
        if (gameOverPanel)   gameOverPanel.SetActive(false);
        if (victoryPanel)    victoryPanel.SetActive(false);
        if (reloadingPanel)  reloadingPanel.SetActive(false);
        if (coverPanel)      coverPanel.SetActive(false);
    }

    void Update()
    {
        // Update gesture debug display
        var bridge = GestureBridge.Instance;
        if (bridge != null)
        {
            if (gestureText)
                gestureText.text = bridge.CurrentGesture != ""
                    ? $"Gesture: {bridge.CurrentGesture} ({bridge.Confidence*100:0}%)"
                    : "No gesture";
            if (actionText)
                actionText.text = bridge.CurrentAction != ""
                    ? $"Action: {bridge.CurrentAction}"
                    : "";
        }

        // Fade hit flash
        if (hitFlashImage && hitFlashImage.color.a > 0)
        {
            var c = hitFlashImage.color;
            c.a -= Time.deltaTime * 4f;
            hitFlashImage.color = c;
        }
    }

    public void UpdateStats(int health, int maxHealth,
                             int ammo, int maxAmmo,
                             int grenades, int maxGrenades)
    {
        // Health bar
        if (healthBar)
        {
            healthBar.value = (float)health / maxHealth;
        }
        if (healthFill)
        {
            float pct = (float)health / maxHealth;
            healthFill.color = pct > 0.5f ? healthColorHigh
                             : pct > 0.25f ? healthColorMid
                             : healthColorLow;
        }
        if (healthText) healthText.text = $"{health}";

        // Ammo
        if (ammoText)    ammoText.text    = $"{ammo}";
        if (ammoMaxText) ammoMaxText.text = $"{maxAmmo}";

        // Grenades
        if (grenadeText) grenadeText.text = new string('●', grenades)
                                          + new string('○', maxGrenades - grenades);
    }

    public void UpdateWave(int wave, int totalWaves, int enemies, int score)
    {
        if (waveText)        waveText.text        = $"WAVE  {wave} / {totalWaves}";
        if (enemiesLeftText) enemiesLeftText.text  = $"ENEMIES  {enemies}";
        if (scoreText)       scoreText.text        = $"{score:000000}";
    }

    public void ShowReloading(bool show)
    {
        if (reloadingPanel) reloadingPanel.SetActive(show);
    }

    public void SetCover(bool inCover)
    {
        if (coverPanel) coverPanel.SetActive(inCover);
        // Tint crosshair red in cover
        Color col = inCover ? new Color(1,0.3f,0.3f,1) : Color.white;
        if (crosshairCenter) crosshairCenter.color = col;
        if (crosshairTop)    crosshairTop.color    = col;
        if (crosshairBottom) crosshairBottom.color = col;
        if (crosshairLeft)   crosshairLeft.color   = col;
        if (crosshairRight)  crosshairRight.color  = col;
    }

    public void ShowHitFlash()
    {
        if (hitFlashImage)
            hitFlashImage.color = new Color(1, 0, 0, 0.45f);
    }

    public void ShowWaveBanner(string msg)
    {
        if (waveBannerText)  waveBannerText.text = msg;
        if (waveBannerGroup) StartCoroutine(FadeBanner());
    }

    IEnumerator FadeBanner()
    {
        if (!waveBannerGroup) yield break;
        waveBannerGroup.alpha = 1f;
        yield return new WaitForSeconds(2f);
        float t = 0;
        while (t < 1f)
        {
            t += Time.deltaTime * 1.5f;
            waveBannerGroup.alpha = 1f - t;
            yield return null;
        }
        waveBannerGroup.alpha = 0;
    }

    public void ShowGameOver(int score)
    {
        if (gameOverPanel) gameOverPanel.SetActive(true);
        if (gameOverScoreText) gameOverScoreText.text = $"SCORE: {score:000000}";
    }

    public void ShowVictory(int score)
    {
        if (victoryPanel) victoryPanel.SetActive(true);
        if (victoryScoreText) victoryScoreText.text = $"FINAL SCORE: {score:000000}";
    }
}
