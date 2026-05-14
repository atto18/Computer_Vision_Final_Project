using UnityEngine;

/// <summary>
/// Grenade — bounces on surfaces, explodes after delay.
/// Attach to grenade prefab.
/// </summary>
public class Grenade : MonoBehaviour
{
    public float fuseTime     = 2.5f;
    public float explosionRadius = 8f;
    public int   damage       = 80;
    public GameObject explosionEffectPrefab;
    public AudioClip  explosionSound;

    private float _timer;
    private bool  _exploded;

    void Update()
    {
        _timer += Time.deltaTime;
        // Spin visually
        transform.Rotate(200f * Time.deltaTime, 300f * Time.deltaTime, 0);
        if (_timer >= fuseTime && !_exploded)
            Explode();
    }

    void Explode()
    {
        _exploded = true;

        if (explosionEffectPrefab)
        {
            var fx = Instantiate(explosionEffectPrefab,
                transform.position, Quaternion.identity);
            Destroy(fx, 3f);
        }

        if (explosionSound)
            AudioSource.PlayClipAtPoint(explosionSound, transform.position, 1f);

        // Damage in radius
        Collider[] hits = Physics.OverlapSphere(transform.position, explosionRadius);
        foreach (var col in hits)
        {
            var pc = col.GetComponentInParent<PlayerController>();
            if (pc != null)
            {
                float dist = Vector3.Distance(transform.position, pc.transform.position);
                pc.TakeDamage(Mathf.RoundToInt(damage * (1f - dist/explosionRadius)));
            }
            var en = col.GetComponentInParent<EnemyAI>();
            if (en != null)
            {
                float dist = Vector3.Distance(transform.position, en.transform.position);
                en.TakeDamage(Mathf.RoundToInt(damage * (1f - dist/explosionRadius)));
            }
        }

        Destroy(gameObject);
    }
}
