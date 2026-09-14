(() => {
  // Pure WebAudio SFX (no external files). Audio requires user gesture.
  let _ac = null;
  const _ctx = () => {
    if (_ac) return _ac;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    _ac = new AC();
    return _ac;
  };

  const _beep = (freq, durMs, type, gain) => {
    const ac = _ctx();
    if (!ac) return;
    if (ac.state === "suspended") ac.resume().catch(() => {});
    const o = ac.createOscillator();
    const g = ac.createGain();
    o.type = type || "sine";
    o.frequency.value = Math.max(60, Number(freq || 440));
    g.gain.value = 0;
    o.connect(g);
    g.connect(ac.destination);
    const t0 = ac.currentTime;
    const d = Math.max(0.03, Number(durMs || 90) / 1000);
    const peak = Math.max(0.01, Math.min(0.15, Number(gain || 0.06)));
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(peak, t0 + 0.015);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + d);
    o.start(t0);
    o.stop(t0 + d + 0.02);
  };

  /** Pitched sweep (cartoon thump / bloop). f0 → f1 down or up. */
  const _toneSweep = (f0, f1, durMs, type, gain) => {
    const ac = _ctx();
    if (!ac) return;
    if (ac.state === "suspended") ac.resume().catch(() => {});
    const o = ac.createOscillator();
    const g = ac.createGain();
    o.type = type || "sine";
    const t0 = ac.currentTime;
    const d = Math.max(0.025, Number(durMs || 80) / 1000);
    const a = Math.max(60, Number(f0 || 440));
    const b = Math.max(60, Number(f1 || 200));
    o.frequency.setValueAtTime(a, t0);
    o.frequency.exponentialRampToValueAtTime(Math.max(60, b), t0 + d);
    const peak = Math.max(0.01, Math.min(0.14, Number(gain || 0.06)));
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(peak, t0 + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + d);
    o.connect(g);
    g.connect(ac.destination);
    o.start(t0);
    o.stop(t0 + d + 0.02);
  };

  const _noise = (durMs, gain, lowpassHz) => {
    const ac = _ctx();
    if (!ac) return;
    if (ac.state === "suspended") ac.resume().catch(() => {});
    const dur = Math.max(0.04, Number(durMs || 140) / 1000);
    const buf = ac.createBuffer(1, Math.floor(ac.sampleRate * dur), ac.sampleRate);
    const data = buf.getChannelData(0);
    // Slightly "softer" noise (avoid harsh hiss on mobile speakers)
    for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * 0.22;
    const src = ac.createBufferSource();
    src.buffer = buf;
    const lp = ac.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = Math.max(300, Number(lowpassHz || 1600));
    const g = ac.createGain();
    g.gain.value = Math.max(0.006, Math.min(0.12, Number(gain || 0.04)));
    src.connect(lp);
    lp.connect(g);
    g.connect(ac.destination);
    src.start();
    src.stop(ac.currentTime + dur + 0.02);
  };

  /** Short band-limited noise burst with envelope (splash / whoosh) */
  const _noiseBurst = (durMs, gain, lowpassHz, highpassHz) => {
    const ac = _ctx();
    if (!ac) return;
    if (ac.state === "suspended") ac.resume().catch(() => {});
    const dur = Math.max(0.03, Number(durMs || 120) / 1000);
    const buf = ac.createBuffer(1, Math.floor(ac.sampleRate * dur), ac.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * 0.28;
    const src = ac.createBufferSource();
    src.buffer = buf;
    const hp = ac.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = Math.max(40, Number(highpassHz || 200));
    const lp = ac.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = Math.max(400, Number(lowpassHz || 2200));
    const g = ac.createGain();
    const t0 = ac.currentTime;
    const peak = Math.max(0.008, Math.min(0.12, Number(gain || 0.04)));
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(peak, t0 + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    src.connect(hp);
    hp.connect(lp);
    lp.connect(g);
    g.connect(ac.destination);
    src.start(t0);
    src.stop(t0 + dur + 0.02);
  };

  const sfx = {
    cast() {
      _beep(320, 70, "sine", 0.032);
      setTimeout(() => _beep(260, 60, "sine", 0.022), 70);
    },
    splash() {
      // Cartoon "satisfying plop": big comedic thump + bright slap + sparkle + tiny bloop
      _toneSweep(340, 95, 58, "sine", 0.068);
      setTimeout(() => _toneSweep(420, 160, 36, "triangle", 0.038), 10);
      _noiseBurst(72, 0.03, 6200, 700);
      setTimeout(() => _noiseBurst(38, 0.016, 9000, 1400), 28);
      setTimeout(() => _toneSweep(780, 420, 32, "sine", 0.014), 72);
      setTimeout(() => _beep(1180, 22, "sine", 0.01), 88);
    },
    bite() {
      _beep(820, 55, "triangle", 0.042);
      setTimeout(() => _beep(980, 55, "triangle", 0.038), 75);
    },
    catch() {
      _beep(520, 85, "sawtooth", 0.03);
      setTimeout(() => _beep(740, 70, "sine", 0.03), 90);
    },
    coin() {
      _beep(880, 45, "sine", 0.03);
      setTimeout(() => _beep(1120, 55, "sine", 0.034), 55);
    },
    thunder() {
      _noise(220, 0.05, 900);
      _beep(86, 220, "sine", 0.06);
    },
  };

  let _enabled = true;
  window.SFX = {
    setEnabled(v) {
      _enabled = !!v;
    },
    cast() { if (_enabled) sfx.cast(); },
    splash() { if (_enabled) sfx.splash(); },
    bite() { if (_enabled) sfx.bite(); },
    catch() { if (_enabled) sfx.catch(); },
    coin() { if (_enabled) sfx.coin(); },
    thunder() { if (_enabled) sfx.thunder(); },
  };
})();

