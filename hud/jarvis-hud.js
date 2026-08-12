(function(){
  // ---------- Synthesized sound effects (Web Audio API) ----------
  const SFX = (function(){
    let ctx = null;
    let masterGain = null;
    let muted = false;
    const STORAGE_KEY = 'jarvis-sfx-muted';

    try{ muted = localStorage.getItem(STORAGE_KEY) === '1'; }catch(e){ /* ignore */ }

    function ensureCtx(){
      if(!ctx){
        ctx = new (window.AudioContext || window.webkitAudioContext)();
        masterGain = ctx.createGain();
        masterGain.gain.value = 0.22;
        masterGain.connect(ctx.destination);
      }
      if(ctx.state === 'suspended'){ ctx.resume(); }
      return ctx;
    }

    function tone(freq, duration, opts){
      opts = opts || {};
      if(muted) return;
      const c = ensureCtx();
      const t0 = c.currentTime + (opts.delay || 0);
      const osc = c.createOscillator();
      const gain = c.createGain();
      osc.type = opts.type || 'sine';
      osc.frequency.setValueAtTime(freq, t0);
      gain.gain.setValueAtTime(opts.startGain || 0.2, t0);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
      osc.connect(gain); gain.connect(masterGain);
      osc.start(t0); osc.stop(t0 + duration + 0.02);
    }

    function sweep(startFreq, endFreq, duration, opts){
      opts = opts || {};
      if(muted) return;
      const c = ensureCtx();
      const t0 = c.currentTime + (opts.delay || 0);
      const osc = c.createOscillator();
      const gain = c.createGain();
      osc.type = opts.type || 'sine';
      osc.frequency.setValueAtTime(startFreq, t0);
      osc.frequency.exponentialRampToValueAtTime(endFreq, t0 + duration);
      gain.gain.setValueAtTime(opts.startGain || 0.2, t0);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
      osc.connect(gain); gain.connect(masterGain);
      osc.start(t0); osc.stop(t0 + duration + 0.02);
    }

    return {
      bootUp(){
        sweep(120, 720, 1.1, {type:'sawtooth', startGain:0.1});
        tone(880, 0.12, {delay:1.15, startGain:0.16});
        tone(1320, 0.18, {delay:1.28, startGain:0.14});
      },
      click(){ tone(720, 0.06, {type:'square', startGain:0.12}); },
      send(){ sweep(500, 900, 0.15, {startGain:0.14}); },
      receive(){
        tone(660, 0.09, {startGain:0.14});
        tone(990, 0.12, {delay:0.08, startGain:0.12});
      },
      listenStart(){ sweep(300, 700, 0.2, {startGain:0.13}); },
      listenStop(){ sweep(700, 300, 0.15, {startGain:0.1}); },
      cardOpen(delay){ sweep(400, 1000, 0.12, {type:'triangle', startGain:0.09, delay: delay || 0}); },
      unlock(){ ensureCtx(); },
      toggleMute(){
        muted = !muted;
        try{ localStorage.setItem(STORAGE_KEY, muted ? '1' : '0'); }catch(e){ /* ignore */ }
        return muted;
      },
      isMuted(){ return muted; }
    };
  })();

  document.addEventListener('pointerdown', function unlockAudioOnce(){
    SFX.unlock();
    document.removeEventListener('pointerdown', unlockAudioOnce);
  }, { once: true });

  const boot = document.getElementById('boot');
  const hud = document.getElementById('hud');
  const stage = document.getElementById('stage');
  const controls = document.getElementById('controls');
  const centerStatus = document.getElementById('center-status');
  const micNote = document.getElementById('mic-note');
  const listenBtn = document.getElementById('listen-btn');
  const speakBtn = document.getElementById('speak-btn');
  const barRingEl = document.getElementById('bar-ring');
  const chatPanel = document.getElementById('chat-panel');
  const chatLog = document.getElementById('chat-log');
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const chatSend = document.getElementById('chat-send');
  const newsLayer = document.getElementById('news-layer');
  const loadingPercentage = document.getElementById('loading-percentage');
  const muteBtn = document.getElementById('mute-btn');

  function refreshMuteBtn(){
    const isMuted = SFX.isMuted();
    muteBtn.textContent = isMuted ? '🔇' : '🔊';
    muteBtn.classList.toggle('muted', isMuted);
  }
  refreshMuteBtn();
  muteBtn.addEventListener('click', ()=>{
    SFX.toggleMute();
    refreshMuteBtn();
    if(!SFX.isMuted()) SFX.click();
  });

  // Create floating particles
  for (let i = 0; i < 30; i++) {
    const particle = document.createElement('div');
    particle.className = 'particle';
    particle.style.left = Math.random() * 100 + '%';
    particle.style.top = Math.random() * 100 + '%';
    particle.style.animationDelay = Math.random() * 3 + 's';
    particle.style.animationDuration = (Math.random() * 3 + 2) + 's';
    document.body.appendChild(particle);
  }

  // ---------- Boot sequence ----------
  hud.classList.add('visible');
  
  let loadPercent = 0;
  const loadingStates = [
    'INITIALIZING CORE SYSTEMS...',
    'LOADING NEURAL NETWORK...',
    'CALIBRATING SENSORS...',
    'ESTABLISHING CONNECTION...',
    'SYSTEM READY...'
  ];
  
  requestAnimationFrame(()=>{
    boot.classList.add('scan');
    boot.classList.add('loading');
    SFX.bootUp();
    
    const loadInterval = setInterval(() => {
      loadPercent += Math.random() * 30;
      if (loadPercent >= 100) {
        loadPercent = 100;
        clearInterval(loadInterval);
        loadingPercentage.textContent = loadingStates[4];
      } else if (loadPercent > 75) {
        loadingPercentage.textContent = loadingStates[3];
      } else if (loadPercent > 50) {
        loadingPercentage.textContent = loadingStates[2];
      } else if (loadPercent > 25) {
        loadingPercentage.textContent = loadingStates[1];
      } else {
        loadingPercentage.textContent = loadingStates[0];
      }
    }, 300);
    
    setTimeout(()=> boot.classList.add('text'), 300);
    setTimeout(()=>{
      boot.classList.add('hide');
      controls.classList.add('visible');
      chatPanel.classList.add('visible');
      muteBtn.classList.add('visible');
    }, 2400);
  });

  // ---------- Build reactive ring ----------
  const BAR_COUNT = 64;
  const bars = [];
  for(let i=0;i<BAR_COUNT;i++){
    const bar = document.createElement('div');
    bar.className = 'bar';
    const angle = (360/BAR_COUNT) * i;
    bar.style.transform = `translate(-50%,-145px) rotate(${angle}deg)`;
    bar.style.transformOrigin = '50% 145px';
    barRingEl.appendChild(bar);
    bars.push(bar);
  }
  function setBarHeights(values){
    for(let i=0;i<BAR_COUNT;i++){
      bars[i].style.height = (6 + values[i]*34) + 'px';
    }
  }
  function resetBars(){ setBarHeights(new Array(BAR_COUNT).fill(0)); }
  resetBars();

  // ---------- Mode / state management ----------
  let mode = 'idle';
  function setMode(next){
    mode = next;
    stage.classList.remove('mode-listening','mode-speaking');
    document.body.classList.remove('mode-listening','mode-speaking');
    if(next === 'listening'){ stage.classList.add('mode-listening'); document.body.classList.add('mode-listening'); }
    if(next === 'speaking'){ stage.classList.add('mode-speaking'); document.body.classList.add('mode-speaking'); }
    centerStatus.textContent = next === 'idle' ? 'IDLE' : next === 'listening' ? 'LISTENING' : 'SPEAKING';
    listenBtn.classList.toggle('active', next === 'listening');
    speakBtn.classList.toggle('active', next === 'speaking');
  }

  // ---------- Microphone reactivity ----------
  let audioCtx, analyser, dataArray, micStream, micRAF;

  async function startListening(){
    if(mode === 'listening'){ stopListening(); return; }
    SFX.listenStart();
    stopSpeakingSim();
    try{
      micStream = await navigator.mediaDevices.getUserMedia({audio:true});
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(micStream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      analyser.smoothingTimeConstant = 0.75;
      source.connect(analyser);
      dataArray = new Uint8Array(analyser.frequencyBinCount);
      setMode('listening');
      micNote.classList.remove('show');
      pumpMic();
    }catch(err){
      micNote.textContent = 'MICROPHONE ACCESS DENIED — RUNNING IN SIMULATED MODE';
      micNote.classList.add('show');
      setMode('listening');
      simulateListening();
    }
  }

  function pumpMic(){
    analyser.getByteFrequencyData(dataArray);
    const bins = dataArray.length;
    const values = new Array(BAR_COUNT);
    for(let i=0;i<BAR_COUNT;i++){ values[i] = dataArray[i % bins] / 255; }
    setBarHeights(values);
    micRAF = requestAnimationFrame(pumpMic);
  }

  let simInterval;
  function simulateListening(){
    simInterval = setInterval(()=>{
      const values = new Array(BAR_COUNT).fill(0).map((_,i)=>{
        const t = Date.now()/500 + i*0.3;
        return Math.max(0, Math.sin(t) * 0.3 + Math.random()*0.15);
      });
      setBarHeights(values);
    }, 60);
  }

  function stopListening(){
    if(mode === 'listening'){ SFX.listenStop(); }
    if(micRAF) cancelAnimationFrame(micRAF);
    if(simInterval) clearInterval(simInterval);
    if(micStream) micStream.getTracks().forEach(t=>t.stop());
    if(audioCtx) audioCtx.close();
    micNote.classList.remove('show');
    resetBars();
    setMode('idle');
  }

  // ---------- Speaking animation ----------
  let speakInterval, speakTimeout;
  function playSpeakingAnimation(durationMs){
    stopListening();
    setMode('speaking');
    let t = 0;
    speakInterval = setInterval(()=>{
      t += 0.12;
      const values = new Array(BAR_COUNT).fill(0).map((_,i)=>{
        const wave = Math.sin(t + i*0.35) * 0.5 + 0.5;
        const envelope = Math.sin(t*0.6) * 0.3 + 0.7;
        return Math.max(0, wave * envelope);
      });
      setBarHeights(values);
    }, 45);
    speakTimeout = setTimeout(stopSpeakingSim, durationMs);
  }
  
  function stopSpeakingSim(){
    if(speakInterval) clearInterval(speakInterval);
    if(speakTimeout) clearTimeout(speakTimeout);
    resetBars();
    if(mode === 'speaking') setMode('idle');
  }

  listenBtn.addEventListener('click', ()=>{ SFX.click(); startListening(); });
  speakBtn.addEventListener('click', ()=>{
    SFX.click();
    if(mode === 'speaking'){ stopSpeakingSim(); return; }
    playSpeakingAnimation(4200);
  });

  // ---------- Chat: talk to FastAPI ----------
  let conversationHistory = [];
  const sessionId = 'browser-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);

  function appendMessage(role, text){
    const el = document.createElement('div');
    el.className = 'msg ' + role;
    el.textContent = text;
    chatLog.appendChild(el);
    chatLog.scrollTop = chatLog.scrollHeight;
    return el;
  }

  function renderMarkdown(text){
    const rawHtml = marked.parse(text, { breaks: true });
    return DOMPurify.sanitize(rawHtml);
  }

  function typeAndRenderMessage(role, fullText){
    const el = document.createElement('div');
    el.className = 'msg ' + role;
    chatLog.appendChild(el);

    const duration = Math.max(400, Math.min(3000, fullText.length * 12));
    const perCharMs = Math.max(4, duration / Math.max(fullText.length, 1));
    let i = 0;

    function tick(){
      i++;
      el.textContent = fullText.slice(0, i);
      chatLog.scrollTop = chatLog.scrollHeight;
      if(i < fullText.length){
        setTimeout(tick, perCharMs);
      }else{
        el.innerHTML = renderMarkdown(fullText);
        // Intercept clicks on video or reel links inside assistant response text
        attachMediaLinkHandlers(el);
        chatLog.scrollTop = chatLog.scrollHeight;
      }
    }
    tick();
    return el;
  }

async function sendToJarvis(message){
  SFX.send();
  appendMessage('user', message);
  chatInput.value = '';
  chatInput.disabled = true;
  chatSend.disabled = true;
  const pending = appendMessage('assistant pending', 'thinking...');

  try{
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ message, history: conversationHistory, session_id: sessionId })
    });
    if(!res.ok) throw new Error('Server error ' + res.status);
    const data = await res.json();

    pending.remove();
    SFX.receive();
    typeAndRenderMessage('assistant', data.reply);
    conversationHistory = data.history;

    const estimatedMs = Math.min(7000, Math.max(1200, data.reply.length * 55));
    playSpeakingAnimation(estimatedMs);

    // Handle cards (both news and video)
    if(data.cards && data.cards.length){
      spawnNewsCards(data.cards);
    }
  }catch(err){
    pending.remove();
    appendMessage('assistant', 'Connection error — is the server running? (' + err.message + ')');
  }finally{
    chatInput.disabled = false;
    chatSend.disabled = false;
    chatInput.focus();
  }
}

  // ---------- In-Place Media & Reel Popup Player ----------

  function playMediaInPopup(embedUrl, title) {
  // Try to open as native video window first (PyQt will catch this)
  if (typeof window.__TAURI__ === 'undefined') {
    // We're in PyQt WebEngine — use console.log to signal the native window
    const videoData = {
      embed_url: embedUrl,
      title: title || 'JARVIS Video Player'
    };
    console.log('JARVIS_OPEN_VIDEO:' + JSON.stringify(videoData));
  } else {
    // Fallback for regular browser: use the overlay
    _playMediaInOverlay(embedUrl, title);
  }
}

function _playMediaInOverlay(rawUrl, title = '') {
  let embedUrl = rawUrl;

  // Handle direct embed URLs (from video cards)
  if (rawUrl.includes('youtube.com/embed/')) {
    embedUrl = rawUrl; // Already an embed URL, use as-is
  } else if (rawUrl.includes('youtube.com/watch?v=')) {
    const videoId = rawUrl.split('v=')[1].split('&')[0];
    embedUrl = `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0&modestbranding=1`;
  } else if (rawUrl.includes('youtu.be/')) {
    const videoId = rawUrl.split('youtu.be/')[1].split('?')[0];
    embedUrl = `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0&modestbranding=1`;
  } else if (rawUrl.includes('youtube.com/shorts/')) {
    const videoId = rawUrl.split('shorts/')[1].split('?')[0];
    embedUrl = `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0&modestbranding=1`;
  } else if (rawUrl.includes('instagram.com/reel/')) {
    const reelId = rawUrl.split('/reel/')[1].split('/')[0];
    embedUrl = `https://www.instagram.com/reel/${reelId}/embed`;
  }

  let overlay = document.getElementById('jarvis-video-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'jarvis-video-overlay';
    overlay.style.cssText = `
      position: fixed; inset: 0; background: rgba(0, 5, 12, 0.85);
      display: flex; justify-content: center; align-items: center;
      z-index: 99999; backdrop-filter: blur(8px);
    `;
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
    document.body.appendChild(overlay);
  }

  const titleBar = title ? `
    <div style="position: absolute; top: 0; left: 0; right: 0; z-index: 10; 
                background: rgba(0,13,20,0.9); border-bottom: 1px solid rgba(0,255,255,0.3);
                padding: 8px 16px; display: flex; align-items: center; gap: 8px;">
      <div style="width: 6px; height: 6px; background: #00d4ff; border-radius: 50%; 
                  box-shadow: 0 0 8px #00d4ff;"></div>
      <span style="font-family: 'Orbitron', sans-serif; font-size: 10px; letter-spacing: 0.15em; 
                   color: #4fd6ff;">${title}</span>
    </div>
  ` : '';

  overlay.innerHTML = `
    <div style="position: relative; width: 85%; max-width: 840px; aspect-ratio: 16/9; 
                border: 1px solid rgba(0,255,255,0.6); box-shadow: 0 0 35px rgba(0,255,255,0.4); 
                border-radius: 12px; overflow: hidden; background: #000;">
      ${titleBar}
      <button onclick="document.getElementById('jarvis-video-overlay').remove()" 
              style="position: absolute; top: ${title ? '36px' : '12px'}; right: 12px; z-index: 10; 
                     background: rgba(255,50,50,0.8); color: #fff; border: none; padding: 6px 14px; 
                     cursor: pointer; border-radius: 20px; font-family: 'Orbitron', sans-serif; 
                     font-size: 10px; letter-spacing: 0.1em;">
        ✕ CLOSE
      </button>
      <iframe src="${embedUrl}" width="100%" height="100%" frameborder="0" 
              allow="autoplay; encrypted-media" allowfullscreen></iframe>
    </div>
  `;
}

  function attachMediaLinkHandlers(container) {
    const links = container.querySelectorAll('a');
    links.forEach(a => {
      const href = a.getAttribute('href') || '';
      if (/youtube\.com|youtu\.be|instagram\.com\/reel/i.test(href)) {
        a.addEventListener('click', (e) => {
          e.preventDefault();
          playMediaInPopup(href);
        });
      }
    });
  }

  // ---------- Direct OS Browser Window Launcher ----------
  const MAX_CARDS = 5;

// Add this function after the existing playMediaInPopup function:

function spawnNewsCards(cards) {
  console.log('[JARVIS] spawnNewsCards called with:', cards.length, 'cards');
  
  const subset = cards.slice(0, MAX_CARDS);
  const videoCards = [];
  const articleCards = [];
  
  subset.forEach(card => {
    console.log('[JARVIS] Card type:', card.type, 'title:', card.title);
    if (card.type === 'video') {
      videoCards.push(card);
    } else {
      articleCards.push(card);
    }
  });
  
  console.log('[JARVIS] Video cards:', videoCards.length, 'Article cards:', articleCards.length);
  
  // Open video cards as native windows
  videoCards.forEach((card, i) => {
    SFX.cardOpen(i * 0.08);
    const embedUrl = card.embed_url || card.url || '';
    const title = card.title || 'JARVIS Video Player';
    
    console.log('[JARVIS] Opening video:', title, 'URL:', embedUrl);
    
    if (embedUrl) {
      // Signal PyQt to open native video window
      const videoData = {
        embed_url: embedUrl,
        title: title
      };
      console.log('JARVIS_OPEN_VIDEO:' + JSON.stringify(videoData));
    }
  });
  
  // Handle regular article cards
  if (articleCards.length > 0) {
    articleCards.forEach((_, i) => SFX.cardOpen(i * 0.08));
    spawnNewsBrowserWindows(articleCards);
  }
}

async function spawnNewsBrowserWindows(cards){
  const blocked = [];
  let successCount = 0;

  // JARVIS Window Grid Dimensions
  const winW = 600;
  const winH = 450;
  const screenW = window.screen.availWidth || 1920;
  const screenH = window.screen.availHeight || 1080;
  const cols = Math.floor(screenW / (winW + 20)) || 1;

  for (let i = 0; i < cards.length; i++) {
    const card = cards[i];
    const targetUrl = card.url && /^https?:\/\//i.test(card.url) ? card.url : null;
    if (!targetUrl) continue;

    // Handle video links directly with popup overlay
    if (/youtube\.com|youtu\.be|instagram\.com\/reel|twitter\.com|tiktok\.com/i.test(targetUrl)) {
      playMediaInPopup(targetUrl);
      SFX.cardOpen(i * 0.08);
      continue;
    }

    // Calculate Grid Layout (Tile across the screen)
    const col = i % cols;
    const row = Math.floor(i / cols);
    const left = 50 + (col * (winW + 20));
    const top = 50 + (row * (winH + 20));

    try {
      const apiUrl = `/open-browser?url=${encodeURIComponent(targetUrl)}&width=${winW}&height=${winH}&left=${left}&top=${top}`;
      const response = await fetch(apiUrl);
      const result = await response.json();
      
      if (result.status === 'success') {
        console.log(`✅ Opened structured window: ${targetUrl}`);
        SFX.cardOpen(i * 0.08);
        successCount++;
      } else {
        console.warn(`⚠️ Failed: ${targetUrl}`, result.message);
        blocked.push(card);
      }
    } catch (error) {
      console.error(`❌ Error opening ${targetUrl}:`, error);
      blocked.push(card);
    }
    
    if (i < cards.length - 1) {
      await new Promise(resolve => setTimeout(resolve, 200));
    }
  }

  if (successCount > 0) {
    appendMessage('assistant', `✅ Structured and deployed ${successCount} window${successCount > 1 ? 's' : ''} to desktop.`);
  }
  
  if (blocked.length) {
    appendBlockedLinks(blocked);
  }
}

  function appendBlockedLinks(cards){
    const wrap = document.createElement('div');
    wrap.className = 'msg assistant';
    const note = document.createElement('div');
    note.textContent = 'Pop-ups were blocked — open your articles here:';
    note.style.marginBottom = '6px';
    wrap.appendChild(note);
    cards.forEach(card=>{
      if(!card.url || !/^https?:\/\//i.test(card.url)) return;
      const a = document.createElement('a');
      a.href = card.url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.className = 'link-pill';
      a.textContent = card.title || 'Open Link';
      wrap.appendChild(a);
    });
    chatLog.appendChild(wrap);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  chatForm.addEventListener('submit', (e)=>{
    e.preventDefault();
    const message = chatInput.value.trim();
    if(!message) return;
    sendToJarvis(message);
  });

  setMode('idle');
})();