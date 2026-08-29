/**
 * J.A.R.V.I.S HUD Controller
 *
 * Modules:
 * - SFX: Sound effects manager
 * - HUD: Visual state and animations
 * - Chat: Message handling and rendering
 * - Browser: External window management via API
 * - Background: Task and briefing management
 * - CV: Resume upload and job search
 */

(function () {
  "use strict";

  // ═══════════════════════════════════════════════════════════════
  // SECTION 1: Sound Effects Manager
  // ═══════════════════════════════════════════════════════════════

  const SFX = (function () {
    let ctx = null;
    let masterGain = null;
    let muted = false;
    const STORAGE_KEY = "jarvis-sfx-muted";

    // Load mute state from localStorage
    try {
      muted = localStorage.getItem(STORAGE_KEY) === "1";
    } catch (e) {
      /* ignore */
    }

    function ensureCtx() {
      if (!ctx) {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
        masterGain = ctx.createGain();
        masterGain.gain.value = 0.22;
        masterGain.connect(ctx.destination);
      }
      if (ctx.state === "suspended") ctx.resume();
      return ctx;
    }

    function tone(freq, duration, opts = {}) {
      if (muted) return;
      const c = ensureCtx();
      const t0 = c.currentTime + (opts.delay || 0);
      const osc = c.createOscillator();
      const gain = c.createGain();
      osc.type = opts.type || "sine";
      osc.frequency.setValueAtTime(freq, t0);
      gain.gain.setValueAtTime(opts.startGain || 0.2, t0);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(t0);
      osc.stop(t0 + duration + 0.02);
    }

    function sweep(startFreq, endFreq, duration, opts = {}) {
      if (muted) return;
      const c = ensureCtx();
      const t0 = c.currentTime + (opts.delay || 0);
      const osc = c.createOscillator();
      const gain = c.createGain();
      osc.type = opts.type || "sine";
      osc.frequency.setValueAtTime(startFreq, t0);
      osc.frequency.exponentialRampToValueAtTime(endFreq, t0 + duration);
      gain.gain.setValueAtTime(opts.startGain || 0.2, t0);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(t0);
      osc.stop(t0 + duration + 0.02);
    }

    return {
      bootUp() {
        sweep(120, 720, 1.1, { type: "sawtooth", startGain: 0.1 });
        tone(880, 0.12, { delay: 1.15, startGain: 0.16 });
        tone(1320, 0.18, { delay: 1.28, startGain: 0.14 });
      },
      click() {
        tone(720, 0.06, { type: "square", startGain: 0.12 });
      },
      send() {
        sweep(500, 900, 0.15, { startGain: 0.14 });
      },
      receive() {
        tone(660, 0.09, { startGain: 0.14 });
        tone(990, 0.12, { delay: 0.08, startGain: 0.12 });
      },
      listenStart() {
        sweep(300, 700, 0.2, { startGain: 0.13 });
      },
      listenStop() {
        sweep(700, 300, 0.15, { startGain: 0.1 });
      },
      cardOpen(delay) {
        sweep(400, 1000, 0.12, {
          type: "triangle",
          startGain: 0.09,
          delay: delay || 0,
        });
      },
      unlock() {
        ensureCtx();
      },
      toggleMute() {
        muted = !muted;
        try {
          localStorage.setItem(STORAGE_KEY, muted ? "1" : "0");
        } catch (e) {
          /* ignore */
        }
        return muted;
      },
      isMuted() {
        return muted;
      },
    };
  })();

  // Unlock audio on first user interaction
  document.addEventListener(
    "pointerdown",
    function unlockAudioOnce() {
      SFX.unlock();
      document.removeEventListener("pointerdown", unlockAudioOnce);
    },
    { once: true },
  );

  // ═══════════════════════════════════════════════════════════════
  // SECTION 2: DOM References
  // ═══════════════════════════════════════════════════════════════

  const DOM = {
    boot: document.getElementById("boot"),
    hud: document.getElementById("hud"),
    stage: document.getElementById("stage"),
    controls: document.getElementById("controls"),
    centerStatus: document.getElementById("center-status"),
    micNote: document.getElementById("mic-note"),
    listenBtn: document.getElementById("listen-btn"),
    speakBtn: document.getElementById("speak-btn"),
    barRingEl: document.getElementById("bar-ring"),
    chatPanel: document.getElementById("chat-panel"),
    chatLog: document.getElementById("chat-log"),
    chatForm: document.getElementById("chat-form"),
    chatInput: document.getElementById("chat-input"),
    chatSend: document.getElementById("chat-send"),
    newsLayer: document.getElementById("news-layer"),
    loadingPercentage: document.getElementById("loading-percentage"),
    muteBtn: document.getElementById("mute-btn"),
    briefingBtn: document.getElementById("briefing-btn"),
    tasksBtn: document.getElementById("tasks-btn"),
    cvBtn: document.getElementById("cv-btn"),
    jobsBtn: document.getElementById("jobs-btn"),
  };

  // ═══════════════════════════════════════════════════════════════
  // SECTION 3: Initialization
  // ═══════════════════════════════════════════════════════════════

  function initMuteButton() {
    function refresh() {
      const isMuted = SFX.isMuted();
      DOM.muteBtn.textContent = isMuted ? "🔇" : "🔊";
      DOM.muteBtn.classList.toggle("muted", isMuted);
    }

    refresh();
    DOM.muteBtn.addEventListener("click", () => {
      SFX.toggleMute();
      refresh();
      if (!SFX.isMuted()) SFX.click();
    });
  }

  function createParticles(count = 30) {
    for (let i = 0; i < count; i++) {
      const particle = document.createElement("div");
      particle.className = "particle";
      particle.style.left = Math.random() * 100 + "%";
      particle.style.top = Math.random() * 100 + "%";
      particle.style.animationDelay = Math.random() * 3 + "s";
      particle.style.animationDuration = Math.random() * 3 + 2 + "s";
      document.body.appendChild(particle);
    }
  }

  function runBootSequence() {
    DOM.hud.classList.add("visible");

    let loadPercent = 0;
    const loadingStates = [
      "INITIALIZING CORE SYSTEMS...",
      "LOADING NEURAL NETWORK...",
      "CALIBRATING SENSORS...",
      "ESTABLISHING CONNECTION...",
      "SYSTEM READY...",
    ];

    requestAnimationFrame(() => {
      DOM.boot.classList.add("scan");
      DOM.boot.classList.add("loading");
      SFX.bootUp();

      const loadInterval = setInterval(() => {
        loadPercent += Math.random() * 30;
        if (loadPercent >= 100) {
          loadPercent = 100;
          clearInterval(loadInterval);
          DOM.loadingPercentage.textContent = loadingStates[4];
        } else if (loadPercent > 75) {
          DOM.loadingPercentage.textContent = loadingStates[3];
        } else if (loadPercent > 50) {
          DOM.loadingPercentage.textContent = loadingStates[2];
        } else if (loadPercent > 25) {
          DOM.loadingPercentage.textContent = loadingStates[1];
        } else {
          DOM.loadingPercentage.textContent = loadingStates[0];
        }
      }, 300);

      setTimeout(() => DOM.boot.classList.add("text"), 300);
      setTimeout(() => {
        DOM.boot.classList.add("hide");
        DOM.controls.classList.add("visible");
        DOM.chatPanel.classList.add("visible");
        DOM.muteBtn.classList.add("visible");
      }, 2400);
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // SECTION 4: HUD Visual State & Audio Reactivity
  // ═══════════════════════════════════════════════════════════════

  const BAR_COUNT = 64;
  const bars = [];

  function buildBarRing() {
    for (let i = 0; i < BAR_COUNT; i++) {
      const bar = document.createElement("div");
      bar.className = "bar";
      const angle = (360 / BAR_COUNT) * i;
      bar.style.transform = `translate(-50%,-145px) rotate(${angle}deg)`;
      bar.style.transformOrigin = "50% 145px";
      DOM.barRingEl.appendChild(bar);
      bars.push(bar);
    }
  }

  function setBarHeights(values) {
    for (let i = 0; i < BAR_COUNT; i++) {
      bars[i].style.height = 6 + values[i] * 34 + "px";
    }
  }

  function resetBars() {
    setBarHeights(new Array(BAR_COUNT).fill(0));
  }

  let mode = "idle";

  function setMode(next) {
    mode = next;
    DOM.stage.classList.remove("mode-listening", "mode-speaking");
    document.body.classList.remove("mode-listening", "mode-speaking");

    if (next === "listening") {
      DOM.stage.classList.add("mode-listening");
      document.body.classList.add("mode-listening");
    }
    if (next === "speaking") {
      DOM.stage.classList.add("mode-speaking");
      document.body.classList.add("mode-speaking");
    }

    DOM.centerStatus.textContent =
      next === "idle"
        ? "IDLE"
        : next === "listening"
          ? "LISTENING"
          : "SPEAKING";
    DOM.listenBtn.classList.toggle("active", next === "listening");
    DOM.speakBtn.classList.toggle("active", next === "speaking");
  }

  // ─── Microphone ───────────────────────────────────────────────

  let audioCtx, analyser, dataArray, micStream, micRAF;
  let simInterval;

  async function startListening() {
    if (mode === "listening") {
      stopListening();
      return;
    }

    SFX.listenStart();
    stopSpeakingSim();

    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(micStream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      analyser.smoothingTimeConstant = 0.75;
      source.connect(analyser);
      dataArray = new Uint8Array(analyser.frequencyBinCount);

      setMode("listening");
      DOM.micNote.classList.remove("show");
      pumpMic();
    } catch (err) {
      DOM.micNote.textContent =
        "MICROPHONE ACCESS DENIED — RUNNING IN SIMULATED MODE";
      DOM.micNote.classList.add("show");
      setMode("listening");
      simulateListening();
    }
  }

  function pumpMic() {
    analyser.getByteFrequencyData(dataArray);
    const bins = dataArray.length;
    const values = new Array(BAR_COUNT);
    for (let i = 0; i < BAR_COUNT; i++) {
      values[i] = dataArray[i % bins] / 255;
    }
    setBarHeights(values);
    micRAF = requestAnimationFrame(pumpMic);
  }

  function simulateListening() {
    simInterval = setInterval(() => {
      const values = new Array(BAR_COUNT).fill(0).map((_, i) => {
        const t = Date.now() / 500 + i * 0.3;
        return Math.max(0, Math.sin(t) * 0.3 + Math.random() * 0.15);
      });
      setBarHeights(values);
    }, 60);
  }

  function stopListening() {
    if (mode === "listening") SFX.listenStop();
    if (micRAF) cancelAnimationFrame(micRAF);
    if (simInterval) clearInterval(simInterval);
    if (micStream) micStream.getTracks().forEach((t) => t.stop());
    if (audioCtx) audioCtx.close();
    DOM.micNote.classList.remove("show");
    resetBars();
    setMode("idle");
  }

  // ─── Speaking Animation ───────────────────────────────────────

  let speakInterval, speakTimeout;

  function playSpeakingAnimation(durationMs) {
    stopListening();
    setMode("speaking");

    let t = 0;
    speakInterval = setInterval(() => {
      t += 0.12;
      const values = new Array(BAR_COUNT).fill(0).map((_, i) => {
        const wave = Math.sin(t + i * 0.35) * 0.5 + 0.5;
        const envelope = Math.sin(t * 0.6) * 0.3 + 0.7;
        return Math.max(0, wave * envelope);
      });
      setBarHeights(values);
    }, 45);

    speakTimeout = setTimeout(stopSpeakingSim, durationMs);
  }

  function stopSpeakingSim() {
    if (speakInterval) clearInterval(speakInterval);
    if (speakTimeout) clearTimeout(speakTimeout);
    resetBars();
    if (mode === "speaking") setMode("idle");
  }

  // ═══════════════════════════════════════════════════════════════
  // SECTION 5: Chat Management
  // ═══════════════════════════════════════════════════════════════

  let conversationHistory = [];
  const sessionId =
    "browser-" +
    Date.now().toString(36) +
    Math.random().toString(36).slice(2, 8);

  function appendMessage(role, text) {
    const el = document.createElement("div");
    el.className = "msg " + role;
    el.textContent = text;
    DOM.chatLog.appendChild(el);
    DOM.chatLog.scrollTop = DOM.chatLog.scrollHeight;
    return el;
  }

  function renderMarkdown(text) {
    const rawHtml = marked.parse(text, { breaks: true });
    return DOMPurify.sanitize(rawHtml);
  }

  function typeAndRenderMessage(role, fullText) {
    const el = document.createElement("div");
    el.className = "msg " + role;
    DOM.chatLog.appendChild(el);

    const duration = Math.max(400, Math.min(3000, fullText.length * 12));
    const perCharMs = Math.max(4, duration / Math.max(fullText.length, 1));
    let i = 0;

    function tick() {
      i++;
      el.textContent = fullText.slice(0, i);
      DOM.chatLog.scrollTop = DOM.chatLog.scrollHeight;

      if (i < fullText.length) {
        setTimeout(tick, perCharMs);
      } else {
        el.innerHTML = renderMarkdown(fullText);
        attachMediaLinkHandlers(el);
        DOM.chatLog.scrollTop = DOM.chatLog.scrollHeight;
      }
    }

    tick();
    return el;
  }

  async function sendToJarvis(message) {
    SFX.send();
    appendMessage("user", message);
    DOM.chatInput.value = "";
    DOM.chatInput.disabled = true;
    DOM.chatSend.disabled = true;

    const pending = appendMessage("assistant pending", "thinking...");

    try {
      // Check for background task requests first
      const taskResponse = await handleBackgroundTaskRequest(message);
      if (taskResponse) {
        pending.remove();
        typeAndRenderMessage("assistant", taskResponse);
        SFX.receive();
        return;
      }

      // Regular chat
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          history: conversationHistory,
          session_id: sessionId,
        }),
      });

      if (!res.ok) throw new Error("Server error " + res.status);
      const data = await res.json();

      pending.remove();
      SFX.receive();
      typeAndRenderMessage("assistant", data.reply);
      conversationHistory = data.history;

      const estimatedMs = Math.min(
        7000,
        Math.max(1200, data.reply.length * 55),
      );
      playSpeakingAnimation(estimatedMs);

      if (data.cards && data.cards.length) {
        spawnCards(data.cards);
      }
    } catch (err) {
      pending.remove();
      appendMessage("assistant", "Connection error: " + err.message);
    } finally {
      DOM.chatInput.disabled = false;
      DOM.chatSend.disabled = false;
      DOM.chatInput.focus();
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // SECTION 6: Browser Window Management
  // ═══════════════════════════════════════════════════════════════

  let openWindows = {};
  let windowCounter = 0;
  const recentlyOpenedUrls = new Set(); // <-- Add this tracker
  const recentlyOpenedVideos = new Set();

  function getYouTubeVideoId(url) {
    try {
      const parsed = new URL(url);

      if (parsed.hostname.includes("youtu.be")) {
        return parsed.pathname.substring(1).split("/")[0];
      }

      if (parsed.pathname === "/watch") {
        return parsed.searchParams.get("v");
      }

      if (parsed.pathname.startsWith("/shorts/")) {
        return parsed.pathname.split("/shorts/")[1].split("/")[0];
      }

      if (parsed.pathname.startsWith("/embed/")) {
        return parsed.pathname.split("/embed/")[1].split("/")[0];
      }
    } catch (e) {
      return null;
    }

    return null;
  }

  async function openInBrowser(url, title = "", options = {}) {
    if (!url || !/^https?:\/\//i.test(url)) return null;

    const youtubeVideoId = getYouTubeVideoId(url);

    if (youtubeVideoId) {
      if (recentlyOpenedVideos.has(youtubeVideoId)) {
        console.log(
          `[JARVIS] Blocked duplicate YouTube video: ${youtubeVideoId}`,
        );
        return null;
      }

      recentlyOpenedVideos.add(youtubeVideoId);

      setTimeout(() => {
        recentlyOpenedVideos.delete(youtubeVideoId);
      }, 10000);
    } else {
      if (recentlyOpenedUrls.has(url)) {
        console.log(`[JARVIS] Blocked duplicate window request: ${url}`);
        return null;
      }

      recentlyOpenedUrls.add(url);

      setTimeout(() => {
        recentlyOpenedUrls.delete(url);
      }, 5000);
    }

    const screenW = window.screen.availWidth || 1920;
    const winW = options.width || 800;
    const winH = options.height || 600;
    const gap = 20;
    const cols = Math.max(1, Math.floor(screenW / (winW + gap)));
    const col = windowCounter % cols;
    const row = Math.floor(windowCounter / cols);

    const windowId =
      "jarvis-" +
      Date.now().toString(36) +
      "-" +
      Math.random().toString(36).slice(2, 6);

    try {
      const params = new URLSearchParams({
        url: url,
        width: winW,
        height: winH,
        left: 50 + col * (winW + gap),
        top: 50 + row * (winH + gap),
        window_id: windowId,
      });

      const res = await fetch(`/open-browser?${params.toString()}`);
      const data = await res.json();

      if (data.status === "success") {
        openWindows[windowId] = {
          url,
          title: title || url,
          openedAt: Date.now(),
        };
        windowCounter++;
        return windowId;
      }
      return null;
    } catch (err) {
      console.error("[JARVIS] Browser open failed:", err);
      return null;
    }
  }

  async function closeBrowserWindow(windowId) {
    if (!openWindows[windowId]) return false;

    try {
      const params = new URLSearchParams({ window_id: windowId });
      const res = await fetch(`/close-browser?${params.toString()}`);
      const data = await res.json();

      if (data.status === "success" || data.status === "not_found") {
        delete openWindows[windowId];
        return true;
      }
      return false;
    } catch (err) {
      console.error("[JARVIS] Browser close failed:", err);
      return false;
    }
  }

  async function closeAllBrowsers() {
    const count = Object.keys(openWindows).length;

    try {
      const res = await fetch("/close-all-browsers");
      const data = await res.json();

      if (data.status === "success") {
        openWindows = {};
        windowCounter = 0;
        if (count > 0) {
          appendMessage(
            "assistant",
            `✅ Closed ${count} browser window${count > 1 ? "s" : ""}.`,
          );
        }
      }
    } catch (err) {
      console.error("[JARVIS] Close all browsers failed:", err);
    }
  }

//   function playMediaInPopup(embedUrl, title) {
//     // Try to open as native video window first (PyQt will catch this)
//     if (typeof window.__TAURI__ === "undefined") {
//       // We're in PyQt WebEngine — use console.log to signal the native window
//       const videoData = {
//         embed_url: embedUrl,
//         title: title || "JARVIS Video Player",
//       };
//       console.log("JARVIS_OPEN_VIDEO:" + JSON.stringify(videoData));
//     } else {
//       // Fallback for regular browser: use the overlay
//       _playMediaInOverlay(embedUrl, title);
//     }
//   }

//   function _playMediaInOverlay(rawUrl, title = '') {
//   let embedUrl = rawUrl;

//   // Handle direct embed URLs (from video cards)
//   if (rawUrl.includes('youtube.com/embed/')) {
//     embedUrl = rawUrl; // Already an embed URL, use as-is
//   } else if (rawUrl.includes('youtube.com/watch?v=')) {
//     const videoId = rawUrl.split('v=')[1].split('&')[0];
//     embedUrl = `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0&modestbranding=1`;
//   } else if (rawUrl.includes('youtu.be/')) {
//     const videoId = rawUrl.split('youtu.be/')[1].split('?')[0];
//     embedUrl = `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0&modestbranding=1`;
//   } else if (rawUrl.includes('youtube.com/shorts/')) {
//     const videoId = rawUrl.split('shorts/')[1].split('?')[0];
//     embedUrl = `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0&modestbranding=1`;
//   } else if (rawUrl.includes('instagram.com/reel/')) {
//     const reelId = rawUrl.split('/reel/')[1].split('/')[0];
//     embedUrl = `https://www.instagram.com/reel/${reelId}/embed`;
//   }

//   let overlay = document.getElementById('jarvis-video-overlay');
//   if (!overlay) {
//     overlay = document.createElement('div');
//     overlay.id = 'jarvis-video-overlay';
//     overlay.style.cssText = `
//       position: fixed; inset: 0; background: rgba(0, 5, 12, 0.85);
//       display: flex; justify-content: center; align-items: center;
//       z-index: 99999; backdrop-filter: blur(8px);
//     `;
//     overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
//     document.body.appendChild(overlay);
//   }

//   const titleBar = title ? `
//     <div style="position: absolute; top: 0; left: 0; right: 0; z-index: 10; 
//                 background: rgba(0,13,20,0.9); border-bottom: 1px solid rgba(0,255,255,0.3);
//                 padding: 8px 16px; display: flex; align-items: center; gap: 8px;">
//       <div style="width: 6px; height: 6px; background: #00d4ff; border-radius: 50%; 
//                   box-shadow: 0 0 8px #00d4ff;"></div>
//       <span style="font-family: 'Orbitron', sans-serif; font-size: 10px; letter-spacing: 0.15em; 
//                    color: #4fd6ff;">${title}</span>
//     </div>
//   ` : '';

//   overlay.innerHTML = `
//     <div style="position: relative; width: 85%; max-width: 840px; aspect-ratio: 16/9; 
//                 border: 1px solid rgba(0,255,255,0.6); box-shadow: 0 0 35px rgba(0,255,255,0.4); 
//                 border-radius: 12px; overflow: hidden; background: #000;">
//       ${titleBar}
//       <button onclick="document.getElementById('jarvis-video-overlay').remove()" 
//               style="position: absolute; top: ${title ? '36px' : '12px'}; right: 12px; z-index: 10; 
//                      background: rgba(255,50,50,0.8); color: #fff; border: none; padding: 6px 14px; 
//                      cursor: pointer; border-radius: 20px; font-family: 'Orbitron', sans-serif; 
//                      font-size: 10px; letter-spacing: 0.1em;">
//         ✕ CLOSE
//       </button>
//       <iframe src="${embedUrl}" width="100%" height="100%" frameborder="0" 
//               allow="autoplay; encrypted-media" allowfullscreen></iframe>
//     </div>
//   `;
// }

  async function playVideoInBrowser(rawUrl, title = "") {
    let watchUrl = rawUrl;

    // Convert embed URLs to regular watch URLs
    if (rawUrl.includes("youtube.com/embed/")) {
      const videoId = rawUrl.split("youtube.com/embed/")[1].split("?")[0];
      watchUrl = `https://www.youtube.com/watch?v=${videoId}`;
    } else if (rawUrl.includes("youtube.com/shorts/")) {
      const videoId = rawUrl.split("shorts/")[1].split("?")[0];
      watchUrl = `https://www.youtube.com/watch?v=${videoId}`;
    }

    return await openInBrowser(watchUrl, title || "YouTube Video", {
      width: 854,
      height: 510,
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // SECTION 7: Card Spawning (News + Video)
  // ═══════════════════════════════════════════════════════════════

  const MAX_CARDS = 5;

  async function spawnCards(cards) {
    const subset = cards.slice(0, MAX_CARDS);
    const videoCards = [];
    const articleCards = [];

    subset.forEach((card) => {
      if (card.type === "video") {
        videoCards.push(card);
      } else {
        articleCards.push(card);
      }
    });

    // Open video cards
    if (videoCards.length > 0) {
      const card = videoCards[0];

      SFX.cardOpen(0);

      const url = card.url || card.embed_url || "";

      if (url) {
        await playVideoInBrowser(url, card.title);
        // await playMediaInPopup(url, card.title);
      }
    }

    // Open article cards with stagger
    for (let i = 0; i < articleCards.length; i++) {
      SFX.cardOpen(i * 0.08);
      const url = articleCards[i].url;
      if (url && /^https?:\/\//i.test(url)) {
        await openInBrowser(url, articleCards[i].title || "Article", {
          width: 600,
          height: 450,
        });
      }
      if (i < articleCards.length - 1) {
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
    }
  }

  function attachMediaLinkHandlers(container) {
    container.querySelectorAll("a").forEach((a) => {
      const href = a.getAttribute("href") || "";

      if (
        /youtube\.com|youtu\.be|instagram\.com\/reel|tiktok\.com/i.test(href)
      ) {
        a.addEventListener("click", (e) => {
          e.preventDefault();
          playVideoInBrowser(href, a.textContent);
        });
      } else if (/^https?:\/\//i.test(href)) {
        a.addEventListener("click", (e) => {
          e.preventDefault();
          openInBrowser(href, a.textContent, { width: 600, height: 450 });
        });
      }
    });
  }

  //   function attachMediaLinkHandlers(container) {
  //   const links = container.querySelectorAll('a');
  //   links.forEach(a => {
  //     const href = a.getAttribute('href') || '';
  //     if (/youtube\.com|youtu\.be|instagram\.com\/reel/i.test(href)) {
  //       a.addEventListener('click', (e) => {
  //         e.preventDefault();
  //         playMediaInPopup(href);
  //       });
  //     }
  //   });
  // }

  // ═══════════════════════════════════════════════════════════════
  // SECTION 8: Background Tasks & Briefing
  // ═══════════════════════════════════════════════════════════════

  async function fetchDailyBriefing() {
    SFX.click();
    appendMessage("user", "Show me my daily briefing");

    try {
      const res = await fetch("/background/briefing");
      const data = await res.json();

      if (data.briefing) {
        typeAndRenderMessage("assistant", data.briefing);
        SFX.receive();
      } else {
        appendMessage("assistant", "No briefing available yet.");
      }
    } catch (err) {
      appendMessage("assistant", "Failed to get briefing: " + err.message);
    }
  }

  async function createJobSearchTask() {
    SFX.click();
    const query = prompt(
      "What opportunities should I look for?",
      "remote software developer jobs",
    );
    if (!query) return;

    appendMessage("user", `Find me ${query} in the background`);

    try {
      const res = await fetch("/background/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "job_search", query, interval_hours: 6 }),
      });
      const data = await res.json();
      appendMessage("assistant", data.message || "Background task created.");
      SFX.receive();
    } catch (err) {
      appendMessage("assistant", "Failed to create task: " + err.message);
    }
  }

  async function handleBackgroundTaskRequest(message) {
    const patterns = [
      { pattern: /find (me )?(.*) jobs?/i, type: "job_search" },
      {
        pattern: /freelance (work|projects?|opportunities?)/i,
        type: "freelance",
      },
      {
        pattern: /monitor|track|watch (.*) (trends?|prices?|news)/i,
        type: "trend_monitor",
      },
      { pattern: /daily (briefing|summary|digest)/i, type: "news_digest" },
    ];

    for (const { pattern, type } of patterns) {
      const match = message.match(pattern);
      if (match) {
        const query = match[2] || match[1] || "general";
        try {
          const res = await fetch("/background/tasks", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type, query, interval_hours: 6 }),
          });
          const data = await res.json();
          return data.message || `Background task created for ${query}`;
        } catch (err) {
          return `Failed to create task: ${err.message}`;
        }
      }
    }
    return null;
  }

  // ═══════════════════════════════════════════════════════════════
  // SECTION 9: CV Upload & Job Search
  // ═══════════════════════════════════════════════════════════════

  function uploadCV() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.docx,.txt";

    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      SFX.click();
      appendMessage("user", `Uploading CV: ${file.name}`);

      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await fetch("/cv/upload", {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        typeAndRenderMessage("assistant", data.message);
        SFX.receive();
      } catch (err) {
        appendMessage("assistant", "Failed to upload CV: " + err.message);
      }
    };

    input.click();
  }

  async function findJobs() {
    SFX.click();
    appendMessage("user", "Find jobs matching my CV");

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: "Find jobs matching my CV and skills",
          history: conversationHistory,
          session_id: sessionId,
        }),
      });
      const data = await res.json();
      typeAndRenderMessage("assistant", data.reply);

      if (data.cards && data.cards.length) {
        spawnCards(data.cards);
      }
      SFX.receive();
    } catch (err) {
      appendMessage("assistant", "Failed to find jobs: " + err.message);
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // SECTION 10: Event Listeners & Initialization
  // ═══════════════════════════════════════════════════════════════

  function setupEventListeners() {
    DOM.listenBtn.addEventListener("click", () => {
      SFX.click();
      startListening();
    });

    DOM.speakBtn.addEventListener("click", () => {
      SFX.click();
      if (mode === "speaking") {
        stopSpeakingSim();
      } else {
        playSpeakingAnimation(4200);
      }
    });

    DOM.chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const message = DOM.chatInput.value.trim();
      if (message) sendToJarvis(message);
    });

    DOM.briefingBtn.addEventListener("click", fetchDailyBriefing);
    DOM.tasksBtn.addEventListener("click", createJobSearchTask);
    DOM.cvBtn.addEventListener("click", uploadCV);
    DOM.jobsBtn.addEventListener("click", findJobs);

    // Keyboard shortcuts
    document.addEventListener("keydown", async (e) => {
      if (e.ctrlKey && e.shiftKey && e.key === "W") {
        e.preventDefault();
        await closeAllBrowsers();
      }
    });

    // Cleanup on unload
    window.addEventListener("beforeunload", () => {
      if (Object.keys(openWindows).length > 0) {
        navigator.sendBeacon("/close-all-browsers");
      }
    });
  }

  function init() {
    initMuteButton();
    createParticles();
    buildBarRing();
    resetBars();
    runBootSequence();
    setupEventListeners();
    setMode("idle");
  }

  // Start everything
  init();
})();
