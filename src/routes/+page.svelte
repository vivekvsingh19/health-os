<script>
  import { onMount, onDestroy } from 'svelte';
  import { isPermissionGranted, requestPermission, sendNotification } from '@tauri-apps/plugin-notification';
  import { enable, isEnabled } from '@tauri-apps/plugin-autostart';
  import { getCurrentWindow } from '@tauri-apps/api/window';

  // ── State ────────────────────────────────────────────────────────────────────
  let status   = 'starting';   // good | bad | no_person | camera_error | offline | starting
  let angle    = null;
  let lastBadNotif = 0;        // epoch ms — cooldown tracking
  const COOLDOWN_MS = 10_000;  // 10 seconds between posture alerts
  const POLL_MS     = 1_000;

  let notifPermitted = false;
  let intervalId;
  let videoMounted = false; // Prevents the video from blinking if a single ping fails

  // ── Auto Popup / Dismiss ────────────────────────────────────────────────────
  const BAD_POPUP_DELAY_MS = 60_000;  // 1 minute of bad posture → popup
  let badStartTime = null;            // when continuous bad posture began
  let windowPopped = false;           // true = window was auto-shown
  let appWindow = null;               // Tauri window handle

  async function handleAutoPopup() {
    if (!appWindow) return;

    if (status === 'bad') {
      // Start tracking bad posture time
      if (badStartTime === null) badStartTime = Date.now();

      const elapsed = Date.now() - badStartTime;
      if (elapsed >= BAD_POPUP_DELAY_MS && !windowPopped) {
        // Bad posture for 1+ minute → show the window!
        windowPopped = true;
        await appWindow.show();
        await appWindow.setFocus();

        if (notifPermitted) {
          sendNotification({
            title: 'HealthOS — Posture Check! 🧘',
            body: 'You\'ve been slouching for over a minute. Look at your screen and fix your posture!',
          }).catch(() => {});
        }
      }
    } else if (status === 'good') {
      // Posture corrected!
      badStartTime = null;

      if (windowPopped) {
        // Wait 3 seconds so the user sees their good posture, then hide
        setTimeout(async () => {
          if (status === 'good' && windowPopped) {
            windowPopped = false;
            await appWindow.hide();
          }
        }, 3000);
      }
    } else {
      // no_person / offline / starting → reset bad tracking
      badStartTime = null;
    }
  }

  // ── Sitting Timer ───────────────────────────────────────────────────────────
  const BREAK_INTERVAL_MS = 60 * 60 * 1000; // 60 minutes
  let sittingStart = null;         // epoch ms when person was first detected
  let sittingMinutes = 0;          // live counter
  let lastBreakNotif = 0;          // prevent spam

  function updateSittingTimer() {
    if (status === 'good' || status === 'bad') {
      if (sittingStart === null) sittingStart = Date.now();
      const elapsed = Date.now() - sittingStart;
      sittingMinutes = Math.floor(elapsed / 60_000);

      // Send break reminder every 60 minutes
      if (elapsed >= BREAK_INTERVAL_MS && notifPermitted) {
        const now = Date.now();
        if (now - lastBreakNotif >= BREAK_INTERVAL_MS) {
          lastBreakNotif = now;
          sendNotification({
            title: 'HealthOS — Time for a Break! 🚶',
            body:  `You've been sitting for ${sittingMinutes} minutes. Stand up, stretch, and walk around!`,
          }).catch(() => {});
        }
      }
    } else {
      // Reset timer if person leaves
      if (status === 'no_person' || status === 'offline') {
        sittingStart = null;
        sittingMinutes = 0;
      }
    }
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────
  function getInstruction(score, status) {
    if (status === 'no_person') return 'Please sit up or adjust your webcam so your shoulders are visible! 📹';
    if (status !== 'good' && status !== 'bad') return '';
    if (score == null) return '';
    if (score >= 90) return 'Perfectly aligned. Keep it up! 🌟';
    if (score >= 60) return 'Slightly slouched. Straighten your back. 📏';
    return 'Pull your shoulders back and lift your chest! 🧘';
  }

  function statusClass(s) {
    if (s === 'good')  return 'good';
    if (s === 'bad')   return 'bad';
    return 'neutral';
  }

  function formatTime(mins) {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  // ── Notification setup ───────────────────────────────────────────────────────
  async function setupNotifications() {
    try {
      notifPermitted = await isPermissionGranted();
      if (!notifPermitted) {
        const perm = await requestPermission();
        notifPermitted = perm === 'granted';
      }
    } catch (e) {
      console.warn('Notification API unavailable:', e);
    }
  }

  // ── Autostart setup ──────────────────────────────────────────────────────────
  async function setupAutostart() {
    try {
      const enabled = await isEnabled();
      if (!enabled) {
        await enable();
        console.log('Autostart enabled');
      }
    } catch (e) {
      console.warn('Autostart setup failed:', e);
    }
  }

  function maybeSendAlert() {
    if (!notifPermitted) return;
    const now = Date.now();
    if (now - lastBadNotif < COOLDOWN_MS) return;
    lastBadNotif = now;
    sendNotification({
      title: 'HealthOS — Bad Posture',
      body:  `Score ${score ?? '?'} — sit up straight! 🧘`,
    }).catch(() => {});
  }

  // ── Polling ──────────────────────────────────────────────────────────────────
  let failedPings = 0;

  async function fetchPosture() {
    try {
      const res  = await fetch('http://127.0.0.1:5000/posture', { signal: AbortSignal.timeout(3000) });
      const data = await res.json();
      status = data.status ?? 'offline';
      angle  = (typeof data.angle === 'number') ? data.angle : null;
      
      if (status !== 'starting' && status !== 'offline' && status !== 'camera_error') {
        videoMounted = true;
        failedPings = 0;
      }

      if (status === 'bad') maybeSendAlert();
      updateSittingTimer();
      await handleAutoPopup();
    } catch {
      failedPings++;
      if (failedPings > 3) {
        status = 'offline';
        videoMounted = false;
      }
      angle  = null;
      updateSittingTimer();
      await handleAutoPopup();
    }
  }

  // ── Lifecycle ────────────────────────────────────────────────────────────────
  onMount(async () => {
    appWindow = getCurrentWindow();
    await setupNotifications();
    await setupAutostart();
    await fetchPosture();
    intervalId = setInterval(fetchPosture, POLL_MS);
  });

  onDestroy(() => clearInterval(intervalId));

  // ── Reactive derived values ──────────────────────────────────────────────────
  $: cls         = statusClass(status);
  $: score       = (angle != null) ? Math.max(0, Math.round(100 - angle)) : null;
  $: instruction = getInstruction(score, status);
</script>

<!-- ── Markup ───────────────────────────────────────────────────────────────── -->
<div class="shell" data-status={cls}>

  <div class="bg-wrapper">
    {#if videoMounted}
      <img class="bg-video" src="http://127.0.0.1:5000/video_feed" alt="Video Feed" />
    {:else}
      <div class="loading-state">
        <span class="loading-icon">⏳</span>
        <p>{status === 'camera_error' ? 'Camera Error' : (status === 'offline' ? 'Connecting to AI Engine...' : 'Starting AI Engine...')}</p>
      </div>
    {/if}
    <div class="video-overlay"></div>
  </div>

  <!-- Top Left Score Badge -->
  {#if score != null}
    <div class="top-score-badge">
      <span class="score-val">{score}</span>
      <span class="score-lbl">SCORE</span>
    </div>
  {/if}

  <!-- Top Right Sitting Timer -->
  {#if sittingMinutes > 0}
    <div class="sitting-timer" class:timer-warn={sittingMinutes >= 50}>
      <span class="timer-icon">🪑</span>
      <span class="timer-val">{formatTime(sittingMinutes)}</span>
    </div>
  {/if}

  <!-- Bottom Centre Guidelines -->
  {#if instruction}
    <div class="bottom-centre-badge">
      <p class="instruction-text">{instruction}</p>
    </div>
  {/if}

</div>

<!-- ── Styles ─────────────────────────────────────────────────────────────────── -->
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  .shell {
    position: relative;
    width: 100vw;
    height: 100vh;
    border-radius: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    user-select: none;
    background: #0a0a0f;
    border: 1px solid rgba(255,255,255,0.09);
    box-shadow:
      0 8px 32px rgba(0,0,0,0.55),
      inset 0 1px 0 rgba(255,255,255,0.07);
    transition: background 0.6s ease, box-shadow 0.6s ease, border-color 0.6s ease;
  }

  .bg-wrapper {
    position: absolute;
    inset: 0;
    z-index: 1;
    overflow: hidden;
    background: #000;
  }

  .bg-video {
    width: 100%;
    height: 100%;
    object-fit: contain;
    transform: scaleX(-1);
  }

  .video-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(to bottom, rgba(10,10,15,0) 40%, rgba(10,10,15,0.6) 75%, rgba(10,10,15,0.95) 100%);
    pointer-events: none;
  }

  .loading-state {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: rgba(255,255,255,0.7);
    font-size: 18px;
    font-weight: 500;
  }
  .loading-icon {
    font-size: 48px;
    margin-bottom: 16px;
    animation: rotate 2s linear infinite;
  }
  @keyframes rotate {
    100% { transform: rotate(360deg); }
  }

  /* ── Bottom Centre Guidelines ───────────────────────────────── */
  .bottom-centre-badge {
    position: absolute;
    bottom: 32px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;
    width: 100%;
    text-align: center;
    pointer-events: none;
  }
  .instruction-text {
    font-size: 16px;
    font-weight: 700;
    color: rgba(255,255,255,1);
    text-shadow: 0 4px 12px rgba(0,0,0,0.9);
    margin: 0;
  }
  .shell[data-status="good"] .instruction-text { color: #4ade80; }
  .shell[data-status="bad"]  .instruction-text { color: #f87171; }

  /* ── Top Left Score ─────────────────────────────────────────── */
  .top-score-badge {
    position: absolute;
    top: 32px;
    left: 32px;
    z-index: 10;
    display: flex;
    flex-direction: column;
    align-items: center;
    background: transparent;
  }
  .score-val {
    font-size: 42px;
    font-weight: 900;
    line-height: 1;
    color: #fff;
    text-shadow: 0 4px 16px rgba(0,0,0,0.8);
  }
  .score-lbl {
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.5px;
    color: rgba(255,255,255,0.85);
    text-shadow: 0 2px 8px rgba(0,0,0,0.9);
    margin-top: 4px;
  }
  .shell[data-status="good"] .score-val { color: rgba(74,222,128,1); }
  .shell[data-status="bad"]  .score-val { color: rgba(248,113,113,1); }

  /* ── Sitting Timer (Top Right) ──────────────────────────────── */
  .sitting-timer {
    position: absolute;
    top: 32px;
    right: 32px;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 8px;
    background: transparent;
  }
  .timer-icon {
    font-size: 20px;
    filter: drop-shadow(0 2px 8px rgba(0,0,0,0.7));
  }
  .timer-val {
    font-size: 18px;
    font-weight: 700;
    color: rgba(255,255,255,0.85);
    text-shadow: 0 2px 8px rgba(0,0,0,0.9);
    font-variant-numeric: tabular-nums;
  }
  .timer-warn .timer-val {
    color: #fbbf24;
    animation: timer-pulse 2s ease-in-out infinite;
  }
  @keyframes timer-pulse {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.6; }
  }
</style>