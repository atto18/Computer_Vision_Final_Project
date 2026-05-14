using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

/// <summary>
/// Listens on UDP port 5065 for gesture commands sent by gesture_bridge.py
/// Parses JSON and exposes current gesture state to all other scripts.
/// </summary>
public class GestureBridge : MonoBehaviour
{
    public static GestureBridge Instance { get; private set; }

    [Header("Network")]
    public int port = 5065;

    // Current gesture state — read by PlayerController
    public string  CurrentGesture   { get; private set; } = "";
    public float   Confidence        { get; private set; } = 0f;
    public string  CurrentAction     { get; private set; } = "";
    public float   HeadYaw           { get; private set; } = 0f;
    public float   HeadPitch         { get; private set; } = 0f;
    public int     HandCount         { get; private set; } = 0;

    // Action flags — set true for one frame then cleared
    public bool    ActionShoot       { get; private set; }
    public bool    ActionGrenade     { get; private set; }
    public bool    ActionReload      { get; private set; }
    public bool    ActionCover       { get; private set; }
    public bool    ActionWalkForward { get; private set; }
    public bool    ActionWalkLeft    { get; private set; }
    public bool    ActionWalkRight   { get; private set; }

    private UdpClient    _udp;
    private Thread       _thread;
    private bool         _running;
    private string       _latestJson = "";
    private bool         _hasNew;
    private readonly object _lock = new object();

    void Awake()
    {
        if (Instance != null && Instance != this) { Destroy(gameObject); return; }
        Instance = this;
        DontDestroyOnLoad(gameObject);
        StartListener();
    }

    void StartListener()
    {
        try
        {
            _udp     = new UdpClient(port);
            _running = true;
            _thread  = new Thread(ReceiveLoop) { IsBackground = true };
            _thread.Start();
            Debug.Log($"[GestureBridge] Listening on UDP:{port}");
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[GestureBridge] Could not start UDP: {e.Message}");
        }
    }

    void ReceiveLoop()
    {
        IPEndPoint ep = new IPEndPoint(IPAddress.Any, 0);
        while (_running)
        {
            try
            {
                byte[] data = _udp.Receive(ref ep);
                string json = Encoding.UTF8.GetString(data);
                lock (_lock) { _latestJson = json; _hasNew = true; }
            }
            catch { }
        }
    }

    void Update()
    {
        // Clear one-frame flags
        ActionShoot = ActionGrenade = ActionReload = ActionCover = false;
        ActionWalkForward = ActionWalkLeft = ActionWalkRight = false;

        string json;
        bool   hasNew;
        lock (_lock) { json = _latestJson; hasNew = _hasNew; _hasNew = false; }
        if (!hasNew || string.IsNullOrEmpty(json)) return;
        Debug.Log("UNITY RECEIVED: " + json);
        try
        {
            GestureData d = JsonUtility.FromJson<GestureData>(json);
            CurrentGesture = d.gesture  ?? "";
            Confidence     = d.confidence;
            CurrentAction  = d.action   ?? "";
            HeadYaw        = d.yaw;
            HeadPitch      = d.pitch;
            HandCount      = d.hand_count;

            switch (CurrentAction)
            {
                case "SHOOT":        ActionShoot        = true; break;
                case "GRENADE":      ActionGrenade      = true; break;
                case "RELOAD":       ActionReload       = true; break;
                case "COVER":        ActionCover        = true; break;
                case "WALK_FORWARD": ActionWalkForward  = true; break;
                case "WALK_LEFT":    ActionWalkLeft     = true; break;
                case "WALK_RIGHT":   ActionWalkRight    = true; break;
            }
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[GestureBridge] JSON parse error: {e.Message}");
        }
    }

    void OnDestroy()
    {
        _running = false;
        _udp?.Close();
        _thread?.Abort();
    }

    [Serializable]
    private class GestureData
    {
        public string gesture;
        public float  confidence;
        public string action;
        public float  yaw;
        public float  pitch;
        public int    hand_count;
    }
}
