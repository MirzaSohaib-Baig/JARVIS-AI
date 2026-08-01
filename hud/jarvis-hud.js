(function(){
  // ---------- Synthesized sound effects (Web Audio API, no audio files) ----------
  // Everything here is generated on the fly with oscillators — no copyrighted
  // movie audio, no asset files to ship, same philosophy as the SVG rings.
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

  // Autoplay policy: a browser tab won't let audio play until you've
  // interacted with the page at least once. The boot chime still tries to
  // play immediately (works right away in the PyQt desktop shell, and in a
  // browser tab if audio was already unlocked earlier this session) — this
  // listener is the fallback that unlocks it on your very first click if
  // that initial attempt got silently blocked.
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
  
  // Simulate loading percentage
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
    
    // Update loading text
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

  // ---------- Build the 64-bar reactive ring ----------
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

  // ---------- Real microphone reactivity ----------
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

  // ---------- Speaking bar animation ----------
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

  // ---------- Chat: talk to the FastAPI backend ----------
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

  // marked converts markdown -> HTML, DOMPurify strips anything unsafe
  // before it touches innerHTML — the reply text ultimately comes from an
  // LLM (and tool results it echoes), so it's treated as untrusted input,
  // not just formatted for looks.
  function renderMarkdown(text){
    const rawHtml = marked.parse(text, { breaks: true });
    return DOMPurify.sanitize(rawHtml);
  }

  // Types the raw text out character-by-character, THEN swaps to rendered
  // markdown once complete. Rendering markdown incrementally mid-type would
  // flash broken partial syntax (a lone "**" before its closing pair
  // arrives) — typing the plain text first and rendering only at the end
  // avoids that without needing a streaming-safe markdown parser.
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

  // ---------- News cards ----------
  const MAX_CARDS = 5;

  function spawnNewsCards(cards){
    const subset = cards.slice(0, MAX_CARDS);
    subset.forEach((_, i)=> SFX.cardOpen(i * 0.08));
    if(window.__TAURI__){
      spawnNewsWindows(subset);
    }else{
      spawnNewsBrowserWindows(subset);
    }
  }

  async function spawnNewsWindows(cards){
    const { WebviewWindow } = window.__TAURI__.webviewWindow;
    const { getCurrentWindow } = window.__TAURI__.window;
    const main = getCurrentWindow();
    const mainPos = await main.outerPosition();
    const mainSize = await main.outerSize();

    cards.forEach((card, i)=>{
      const params = new URLSearchParams({
        title: card.title, source: card.source, body: card.body, url: card.url, image: card.image, delay: i * 120
      });
      const x = mainPos.x + mainSize.width * 0.15 + i * 40 + (i % 2 === 0 ? -60 : 260);
      const y = mainPos.y + 80 + i * 70;

      new WebviewWindow(`news-${Date.now()}-${i}`, {
        url: `/card?${params.toString()}`,
        title: card.source || 'JARVIS',
        width: 300, height: 200,
        x, y,
        decorations: false,
        transparent: true,
        resizable: true,
        shadow: true,
      });
    });
  }

  function spawnNewsBrowserWindows(cards){
    const blocked = [];
    const screenW = window.screen.availWidth || 1280;
    const screenH = window.screen.availHeight || 800;
    const winW = 340, winH = 260;

    cards.forEach((card, i)=>{
      const params = new URLSearchParams({
        title: card.title, source: card.source, body: card.body, url: card.url, image: card.image, delay: i * 120
      });
      
      const GAP = 20;
      const columns = Math.floor(screenW / (winW + GAP));
      const row = Math.floor(i / columns);
      const col = i % columns;
      const left = 40 + col * (winW + GAP);
      const top = 40 + row * (winH + GAP);
      
      const features = `width=${winW},height=${winH},left=${left},top=${top},resizable=yes,scrollbars=no,status=no,toolbar=no,menubar=no,location=no`;
      const w = window.open(`/card?${params.toString()}`, `jarvis-news-${Date.now()}-${i}`, features);
      if(!w){ blocked.push(card); }
    });

    if(blocked.length){
      appendBlockedLinks(blocked);
    }
  }

  function appendBlockedLinks(cards){
    const wrap = document.createElement('div');
    wrap.className = 'msg assistant';
    const note = document.createElement('div');
    note.textContent = 'Your browser blocked some pop-up windows — open them directly:';
    note.style.marginBottom = '6px';
    wrap.appendChild(note);
    cards.forEach(card=>{
      if(!card.url || !/^https?:\/\//i.test(card.url)) return;
      const a = document.createElement('a');
      a.href = card.url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.className = 'link-pill';
      a.textContent = card.title;
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