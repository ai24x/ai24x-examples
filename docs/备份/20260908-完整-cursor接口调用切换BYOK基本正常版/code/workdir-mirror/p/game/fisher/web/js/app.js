(() => {
  const LS = {
    api: "ai24x_fisher_api_base",
    dev: "ai24x_fisher_dev_key",
    tok: "ai24x_fisher_token",
    theme: "ai24x_fisher_theme",
    sfx: "ai24x_fisher_sfx",
  };

  const $ = (id) => document.getElementById(id);

  const now = () => new Date().toISOString().replace("T", " ").replace("Z", "");

  const log = (obj) => {
    const el = $("log");
    const t = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
    el.textContent = `[${now()}] ${t}\n\n` + el.textContent;
  };

  const friendlyError = (action, e) => {
    const status = e && typeof e.status === "number" ? e.status : null;
    const detail = e && e.data ? e.data.detail : null;
    if (status === 401 && detail === "Missing bearer token") {
      return `未登录：请先点击「dev-login」获取 token，再执行 ${action}。`;
    }
    if (status === 429 && detail && detail.code === "cooldown") {
      return `冷却中：请等待 ${detail.retry_after_s}s 后再钓鱼。`;
    }
    if (status) {
      return `请求失败（${status} ${e.statusText || ""}）：${typeof detail === "string" ? detail : "见原始输出"}`;
    }
    return "请求失败：见原始输出";
  };

  const logEvent = (evt) => {
    // evt: { ok, action, out? , error? }
    if (typeof evt === "string") return log(evt);
    const head = evt.ok ? "✅" : "❌";
    const summary =
      evt.ok
        ? `${head} ${evt.action} 成功`
        : `${head} ${evt.action} 失败：${friendlyError(evt.action, evt.error)}`;
    const raw = JSON.stringify(evt, null, 2);
    log(`${summary}\n${raw}`);
  };

  const getApiBase = () =>
    (localStorage.getItem(LS.api) || "http://127.0.0.1:18041").trim().replace(/\/$/, "");

  const getDevKey = () => (localStorage.getItem(LS.dev) || "web-dev-001").trim();

  const getToken = () => (localStorage.getItem(LS.tok) || "").trim();

  const setToken = (tok) => localStorage.setItem(LS.tok, tok || "");

  const refreshPills = () => {
    $("api-pill").textContent = getApiBase();
    $("dev-pill").textContent = getDevKey();
    const tok = getToken();
    $("tok-pill").textContent = tok ? `${tok.slice(0, 10)}…` : "(empty)";
  };

  // Tiny SFX (no external files). Audio requires user gesture.
  let _ac = null;
  const sfxEnabled = () => (localStorage.getItem(LS.sfx) || "on").trim() !== "off";
  const _audioCtx = () => {
    if (_ac) return _ac;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    _ac = new AC();
    return _ac;
  };
  const _beep = (freq, durMs, type, gain) => {
    if (!sfxEnabled()) return;
    const ac = _audioCtx();
    if (!ac) return;
    if (ac.state === "suspended") ac.resume().catch(() => {});
    const o = ac.createOscillator();
    const g = ac.createGain();
    o.type = type || "sine";
    o.frequency.value = Math.max(80, Number(freq || 440));
    g.gain.value = 0;
    o.connect(g);
    g.connect(ac.destination);
    const t0 = ac.currentTime;
    const d = Math.max(0.03, Number(durMs || 90) / 1000);
    const peak = Math.max(0.01, Math.min(0.12, Number(gain || 0.05)));
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(peak, t0 + 0.015);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + d);
    o.start(t0);
    o.stop(t0 + d + 0.02);
  };
  const sfx = {
    cast() {
      _beep(320, 70, "sine", 0.032);
    },
    plop() {
      _beep(180, 90, "sine", 0.03);
      setTimeout(() => _beep(140, 80, "sine", 0.024), 60);
    },
    bite() {
      _beep(820, 55, "triangle", 0.042);
      setTimeout(() => _beep(980, 55, "triangle", 0.038), 75);
    },
    pull() {
      _beep(520, 85, "sawtooth", 0.032);
    },
    sell() {
      _beep(660, 50, "sine", 0.028);
      setTimeout(() => _beep(880, 60, "sine", 0.032), 65);
    },
  };

  // Fish catalog for UI rendering (same as server fish_catalog.py)
  const SPECIES = [
    { id: 1, name: "白条", currency: "coin", unit_value: 8 },
    { id: 2, name: "小鲫鱼", currency: "coin", unit_value: 12 },
    { id: 3, name: "麦穗鱼", currency: "coin", unit_value: 10 },
    { id: 4, name: "小鲤鱼", currency: "coin", unit_value: 18 },
    { id: 5, name: "罗非鱼", currency: "coin", unit_value: 22 },
    { id: 6, name: "草鱼", currency: "coin", unit_value: 35 },
    { id: 7, name: "青鱼", currency: "coin", unit_value: 48 },
    { id: 8, name: "黑鱼", currency: "coin", unit_value: 55 },
    { id: 9, name: "鲶鱼", currency: "coin", unit_value: 52 },
    { id: 10, name: "巨型鲤鱼", currency: "coin", unit_value: 68 },
    { id: 11, name: "小黄鱼", currency: "score", unit_value: 2 },
    { id: 12, name: "带鱼", currency: "score", unit_value: 3 },
    { id: 13, name: "海鲈", currency: "score", unit_value: 5 },
    { id: 14, name: "鲷鱼", currency: "score", unit_value: 6 },
    { id: 15, name: "变异浅海巨鱼", currency: "score", unit_value: 12 },
  ];
  const SP_BY_ID = new Map(SPECIES.map((s) => [String(s.id), s]));

  // UI state
  let cooldownEndsAtMs = 0;
  let lastCooldownTotalMs = 0;
  let cooldownTimer = null;
  let phase = "idle"; // idle | waiting | bite | cooldown
  let biteTimer = null;
  let busy = false;

  const setBusy = (v) => {
    busy = !!v;
    const cast = $("btnCast");
    const pull = $("btnPull");
    const sell = $("btnSellAll");
    if (cast) cast.disabled = busy;
    if (pull) pull.disabled = busy;
    if (sell) sell.disabled = busy;
  };

  const setPhase = (p, hint) => {
    phase = p;
    const pt = $("phaseText");
    const ht = $("hintText");
    if (pt) {
      const map = { idle: "空闲", waiting: "等待咬钩", bite: "已咬钩", cooldown: "冷却中" };
      pt.textContent = map[p] || String(p);
    }
    if (ht && hint != null) ht.textContent = String(hint);

    const cast = $("btnCast");
    const pull = $("btnPull");
    if (cast) cast.classList.toggle("primary", true);
    if (pull) pull.classList.remove("hide");

    if (p === "idle") {
      const w = $("water");
      if (w) w.classList.remove("is-waiting", "is-bite", "is-cooldown");
      if (cast) cast.textContent = "抛竿";
      if (pull) pull.classList.add("hide");
    } else if (p === "waiting") {
      const w = $("water");
      if (w) {
        w.classList.add("is-waiting");
        w.classList.remove("is-bite", "is-cooldown");
      }
      if (cast) cast.textContent = "等待…";
      if (pull) pull.classList.add("hide");
    } else if (p === "bite") {
      const w = $("water");
      if (w) {
        w.classList.add("is-bite");
        w.classList.remove("is-waiting", "is-cooldown");
      }
      if (cast) cast.textContent = "已咬钩";
      if (pull) pull.classList.remove("hide");
      if (pull) pull.textContent = "收竿";
    } else if (p === "cooldown") {
      const w = $("water");
      if (w) {
        w.classList.add("is-cooldown");
        w.classList.remove("is-waiting", "is-bite");
      }
      if (cast) cast.textContent = "冷却中";
      if (pull) pull.classList.add("hide");
    }
  };

  const clearBiteTimer = () => {
    if (biteTimer) {
      clearTimeout(biteTimer);
      biteTimer = null;
    }
  };

  const toast = (msg) => {
    const t = $("toast");
    if (!t) return;
    t.textContent = String(msg || "");
    t.classList.add("is-on");
    clearTimeout(toast._tm);
    toast._tm = setTimeout(() => t.classList.remove("is-on"), 1400);
  };

  const ring = () => {
    const r = $("ring");
    if (!r) return;
    r.classList.remove("is-on");
    // force reflow
    void r.offsetWidth;
    r.classList.add("is-on");
  };

  const setBite = (on) => {
    const b = $("bobber");
    if (!b) return;
    // legacy class toggles kept for compatibility; new float uses .water state for animation
    b.classList.toggle("is-bite", !!on);
    b.classList.toggle("is-float", !on);
  };

  const _clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  const setTug = (tug01, bend01) => {
    const w = $("water");
    if (!w) return;
    const t = _clamp(Number(tug01 || 0), 0, 1);
    const b = _clamp(Number(bend01 != null ? bend01 : tug01 || 0), 0, 1);
    w.style.setProperty("--tug", String(t.toFixed(3)));
    w.style.setProperty("--bend", String(b.toFixed(3)));
  };

  const setBobberPos = (xPct, yPct) => {
    const w = $("water");
    if (!w) return;
    const x = _clamp(Number(xPct), 0, 100);
    const y = _clamp(Number(yPct), 0, 100);
    w.style.setProperty("--bobX", `${x.toFixed(2)}%`);
    w.style.setProperty("--bobY", `${y.toFixed(2)}%`);
  };

  const getTipPct = () => {
    const water = $("water");
    const tip = $("rodTip");
    if (!water || !tip) return { x: 78, y: 26 };
    const wr = water.getBoundingClientRect();
    const tr = tip.getBoundingClientRect();
    if (!wr.width || !wr.height) return { x: 78, y: 26 };
    const x = ((tr.left + tr.width / 2 - wr.left) / wr.width) * 100;
    const y = ((tr.top + tr.height / 2 - wr.top) / wr.height) * 100;
    return { x: _clamp(x, 0, 100), y: _clamp(y, 0, 100) };
  };

  const fishStrength01 = (fishOut) => {
    // Map "value" to strength; works for both coin/score fish
    const v = Math.max(0, Number(fishOut?.unit_value ?? 0));
    // Soft cap: small fish 0.25..0.45, big fish 0.65..0.95
    const s = 0.22 + Math.log(1 + v) / Math.log(1 + 80);
    return _clamp(s, 0.18, 0.95);
  };

  // Dynamic rod-line + underwater shadows (pure CSS/JS; no external assets)
  const updateRodAndLine = () => {
    const water = $("water");
    const bob = $("bobber");
    const p = $("linePath");
    const svg = $("lineSvg");
    const rodSvg = $("rodSvg");
    const rodPath = $("rodPath");
    const rodGrip = $("rodGrip");
    const rodTip = $("rodTip");
    const g1 = $("rodG1");
    const g2 = $("rodG2");
    const g3 = $("rodG3");
    if (!water || !bob || !p || !svg || !rodSvg || !rodPath || !rodGrip || !rodTip) return;

    const wr = water.getBoundingClientRect();
    const br = bob.getBoundingClientRect();

    // Rod geometry in rodSvg viewBox coords (0..100). We bend by --bend (0..1)
    const bend = _clamp(Number(getComputedStyle(water).getPropertyValue("--bend") || 0), 0, 1);
    const t = 0.55 + bend * 0.95; // bend factor
    const base = { x: 86, y: 92 };
    const tip0 = { x: 22, y: 28 };
    const c1 = { x: 72, y: 74 };
    const c2 = { x: 46 - t * 10, y: 44 + t * 8 };
    const tip = { x: tip0.x - t * 6, y: tip0.y + t * 10 };

    rodPath.setAttribute(
      "d",
      `M ${base.x} ${base.y} C ${c1.x} ${c1.y} ${c2.x} ${c2.y} ${tip.x} ${tip.y}`,
    );
    rodGrip.setAttribute("d", `M 86 92 C 83 90 80 86 77 80`);
    rodTip.setAttribute("cx", String(tip.x));
    rodTip.setAttribute("cy", String(tip.y));
    if (g1) { g1.setAttribute("cx", String(62)); g1.setAttribute("cy", String(66)); }
    if (g2) { g2.setAttribute("cx", String(44 - t * 3)); g2.setAttribute("cy", String(52 + t * 2)); }
    if (g3) { g3.setAttribute("cx", String(30 - t * 4)); g3.setAttribute("cy", String(40 + t * 4)); }

    // Convert rod tip point to water-percent coords (for line start)
    const rr = rodSvg.getBoundingClientRect();
    const tipAbsX = rr.left + (tip.x / 100) * rr.width;
    const tipAbsY = rr.top + (tip.y / 100) * rr.height;
    const x1 = ((tipAbsX - wr.left) / wr.width) * 100;
    const y1 = ((tipAbsY - wr.top) / wr.height) * 100;
    const x2 = ((br.left + br.width / 2 - wr.left) / wr.width) * 100;
    const y2 = ((br.top + br.height * 0.55 - wr.top) / wr.height) * 100; // tie point near "waterline" on bobber

    const dx = x2 - x1;
    const dy = y2 - y1;
    const dist = Math.hypot(dx, dy);
    const sag = _clamp(6 + dist * 0.05 + bend * 6, 8, 24);

    const cx1 = x1 + dx * 0.32;
    const cy1 = y1 + dy * 0.18 + sag;
    const cx2 = x1 + dx * 0.72;
    const cy2 = y1 + dy * 0.66 + sag;
    p.setAttribute("d", `M ${x1.toFixed(2)} ${y1.toFixed(2)} C ${cx1.toFixed(2)} ${cy1.toFixed(2)} ${cx2.toFixed(2)} ${cy2.toFixed(2)} ${x2.toFixed(2)} ${y2.toFixed(2)}`);

    // keep a stable viewBox; we draw in 0..100 normalized coords
    svg.setAttribute("viewBox", "0 0 100 100");
  };

  let _fish = [];
  const initFishShadows = () => {
    const layer = $("fishLayer");
    if (!layer) return;
    layer.innerHTML = "";
    const n = 6;
    _fish = new Array(n).fill(0).map((_, i) => {
      const el = document.createElement("div");
      el.className = "fish-shadow";
      layer.appendChild(el);
      const seed = Math.random() * 1000 + i * 77;
      return {
        el,
        seed,
        x: 10 + Math.random() * 80,
        y: 64 + Math.random() * 30,
        spd: 10 + Math.random() * 22,
        dir: Math.random() < 0.5 ? -1 : 1,
        w: 70 + Math.random() * 70,
      };
    });
  };

  const _fishTick = (t) => {
    const water = $("water");
    if (!water) return;
    const wr = water.getBoundingClientRect();
    if (!wr.width || !wr.height) return;
    const bob = $("bobber");
    const br = bob ? bob.getBoundingClientRect() : null;
    const bobY = br ? ((br.top + br.height / 2 - wr.top) / wr.height) * 100 : 56;
    const bobX = br ? ((br.left + br.width / 2 - wr.left) / wr.width) * 100 : 50;

    const isBite = phase === "bite";
    const isWaiting = phase === "waiting";
    const speedMul = isBite ? 1.55 : isWaiting ? 1.15 : 1.0;

    for (const f of _fish) {
      // slow drift with gentle turns; keep them in lower water region
      f.x += (f.dir * f.spd * speedMul * 0.016) * (wr.width / 540);
      const wob = Math.sin((t / 1000) * 1.2 + f.seed) * 0.9;
      f.y += wob * 0.06;

      if (f.x < -10) {
        f.x = 110;
        f.y = 66 + Math.random() * 28;
      }
      if (f.x > 110) {
        f.x = -10;
        f.y = 66 + Math.random() * 28;
      }
      f.y = _clamp(f.y, 62, 94);

      // when bite, one shadow approaches bobber subtly (as if fish circling)
      const near =
        isBite && Math.abs(f.x - bobX) < 18 && Math.abs(f.y - (bobY + 18)) < 18 ? 1 : 0;
      const opacity = 0.28 + (near ? 0.24 : 0) + (isWaiting ? 0.06 : 0);
      const scale = 0.92 + (near ? 0.22 : 0) + (Math.sin((t / 1000) * 0.9 + f.seed) * 0.05);

      f.el.style.left = `${f.x.toFixed(2)}%`;
      f.el.style.top = `${f.y.toFixed(2)}%`;
      f.el.style.width = `${f.w.toFixed(0)}px`;
      f.el.style.opacity = String(_clamp(opacity, 0.12, 0.72));
      f.el.style.transform = `translate(-50%,-50%) scaleX(${(1.15 * scale).toFixed(3)}) scaleY(${(0.95 * scale).toFixed(3)})`;
    }
  };

  let _raf = null;
  const startSceneLoop = () => {
    if (_raf) return;
    const tick = (t) => {
      updateRodAndLine();
      _fishTick(t || performance.now());
      _raf = requestAnimationFrame(tick);
    };
    _raf = requestAnimationFrame(tick);
  };

  const renderInventory = (inv) => {
    const root = $("inventory");
    if (!root) return;
    const entries = Object.entries(inv || {}).filter(([, n]) => Number(n) > 0);
    if (!entries.length) {
      root.innerHTML = `<div class="inv-item"><div><div class="n">空空如也</div><div class="m">去钓一条鱼吧</div></div><div class="m">🎣</div></div>`;
      return;
    }
    entries.sort((a, b) => Number(a[0]) - Number(b[0]));
    root.innerHTML = entries
      .map(([sid, n]) => {
        const sp = SP_BY_ID.get(String(sid));
        const nm = sp ? sp.name : `鱼#${sid}`;
        const cur = sp ? (sp.currency === "coin" ? "金币鱼" : "积分鱼") : "未知";
        const val = sp ? `${sp.unit_value}${sp.currency === "coin" ? "金" : "分"}/条` : "-";
        const ico = `assets/fish/${encodeURIComponent(String(sid))}.svg`;
        return `<div class="inv-item">
  <div class="ico" title="${nm}"><img alt="${nm}" src="${ico}" loading="lazy" /></div>
  <div style="min-width:0">
    <div class="n">${nm} <span class="m">× ${Number(n)}</span></div>
    <div class="m">${cur} · ${val}</div>
  </div>
  <div class="rightTag">仓库</div>
</div>`;
      })
      .join("");
  };

  const renderMe = (me) => {
    if (!me) return;
    const coins = $("coins");
    const score = $("score");
    const spot = $("spotName");
    const rod = $("rodLevel");
    if (coins) coins.textContent = String(me.coins ?? "-");
    if (score) score.textContent = String(me.score ?? "-");
    if (spot) spot.textContent = String(me.spot_name ?? "-");
    if (rod) rod.textContent = String(me.rod_level ?? 0);
    renderInventory(me.inventory || {});
  };

  const startCooldown = (seconds) => {
    const s = Math.max(0, Number(seconds || 0));
    lastCooldownTotalMs = s * 1000;
    cooldownEndsAtMs = Date.now() + lastCooldownTotalMs;
    if (cooldownTimer) clearInterval(cooldownTimer);
    cooldownTimer = setInterval(tickCooldown, 120);
    tickCooldown();
  };

  const tickCooldown = () => {
    const txt = $("cooldownText");
    const bar = $("cooldownBar");
    const cast = $("btnCast");
    if (!txt || !bar || !cast) return;
    const nowMs = Date.now();
    const remain = Math.max(0, cooldownEndsAtMs - nowMs);
    if (remain <= 0) {
      txt.textContent = "就绪";
      bar.style.width = "0%";
      cast.disabled = busy;
      setPhase("idle", "点击「抛竿」开始");
      if (cooldownTimer) {
        clearInterval(cooldownTimer);
        cooldownTimer = null;
      }
      return;
    }
    const remainS = Math.ceil(remain / 1000);
    txt.textContent = `${remainS}s`;
    const pct = lastCooldownTotalMs ? Math.min(100, Math.max(0, (remain / lastCooldownTotalMs) * 100)) : 0;
    bar.style.width = `${pct.toFixed(1)}%`;
    cast.disabled = true;
    setPhase("cooldown", "冷却结束后再抛竿");
  };

  const syncInputs = () => {
    $("apiBase").value = getApiBase();
    $("devKey").value = getDevKey();
    $("theme").value = (localStorage.getItem(LS.theme) || "calm").trim() || "calm";
    refreshPills();
  };

  const api = async (path, method, body) => {
    const url = `${getApiBase()}${path}`;
    const headers = { "content-type": "application/json" };
    const tok = getToken();
    if (tok) headers.authorization = `Bearer ${tok}`;
    const opt = { method: method || "GET", headers };
    if (body != null && (method || "GET") !== "GET") opt.body = JSON.stringify(body);

    const res = await fetch(url, opt);
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }
    if (!res.ok) throw { status: res.status, statusText: res.statusText, data };
    return data;
  };

  const doLogin = async () => {
    const out = await api("/v1/auth/dev-login", "POST", { dev_key: getDevKey() });
    if (!out || !out.access_token) throw { message: "missing access_token", out };
    setToken(out.access_token);
    refreshPills();
    logEvent({ ok: true, action: "dev-login", out });
  };

  const doMe = async () => {
    const out = await api("/v1/me", "GET");
    renderMe(out);
    logEvent({ ok: true, action: "me", out });
  };

  const castRod = async () => {
    if (phase === "cooldown") {
      toast("冷却中，稍后再抛竿");
      return;
    }
    if (phase !== "idle") return;
    clearBiteTimer();
    const w = $("water");
    const tip = getTipPct();
    // throw: start at rod tip -> land on surface line
    setBobberPos(tip.x, tip.y);
    setTimeout(() => setBobberPos(50, 54), 40);
    if (w) {
      w.classList.remove("is-cast");
      // force reflow
      void w.offsetWidth;
      w.classList.add("is-cast");
      setTimeout(() => w.classList.remove("is-cast"), 320);
    }
    ring();
    setBite(false);
    setTug(0, 0);
    setPhase("waiting", "静待鱼讯…");
    toast("已抛竿，静待鱼讯…");
    sfx.cast();
    setTimeout(() => sfx.plop(), 220);
    const ms = 1500 + Math.floor(Math.random() * 2200);
    biteTimer = setTimeout(() => {
      biteTimer = null;
      setBite(true);
      // Unknown fish yet; simulate bite strength for anticipation
      setTug(0.35 + Math.random() * 0.45, 0.25 + Math.random() * 0.35);
      setPhase("bite", "鱼已咬钩！点击「收竿」");
      toast("鱼已咬钩！");
      sfx.bite();
    }, ms);
  };

  const pullRod = async () => {
    if (phase !== "bite") {
      toast("还没咬钩，先抛竿等待");
      return;
    }
    clearBiteTimer();
    sfx.pull();
    // now we call server to roll fish (truth source)
    const out = await api("/v1/game/fish", "POST", {});
    // After knowing actual fish, apply stronger/weaker tug (big fish = more violent)
    const s = fishStrength01(out);
    setTug(s, _clamp(0.18 + s * 0.95, 0, 1));
    // quick snap-down moment
    setTimeout(() => setTug(Math.max(0, s * 0.55), Math.max(0, s * 0.65)), 520);
    ring();
    toast(`上鱼：${out.name}（+1）`);
    setBite(false);
    // relax rod a bit once bite ends
    setTimeout(() => setTug(0, 0), 900);
    setPhase("cooldown", "结算完成，进入冷却");
    if (out && out.cooldown_s) startCooldown(out.cooldown_s);
    await doMe();
    logEvent({ ok: true, action: "fish", out });
  };

  const doSellAll2 = async () => {
    const out = await api("/v1/game/sell", "POST", { sell_all: true });
    const msg =
      out.coins_delta
        ? `出售成功：金币 +${out.coins_delta}`
        : out.score_delta
          ? `出售成功：积分 +${out.score_delta}`
          : "无可出售的鱼";
    toast(msg);
    if (out.coins_delta || out.score_delta) sfx.sell();
    await doMe();
    logEvent({ ok: true, action: "sell_all", out });
  };

  const setTheme = (t) => {
    const v = String(t || "").trim() || "calm";
    localStorage.setItem(LS.theme, v);
    document.documentElement.setAttribute("data-theme", v);
  };

  const wire = () => {
    const sm = $("settingsModal");
    const openSettings = () => {
      if (!sm) return;
      sm.classList.remove("hide");
      toast("已打开设置（不影响游戏）");
    };
    const closeSettings = () => {
      if (!sm) return;
      sm.classList.add("hide");
    };
    const btnSet = $("btnSettings");
    const btnSetClose = $("btnSettingsClose");
    if (btnSet) btnSet.addEventListener("click", openSettings);
    if (btnSetClose) btnSetClose.addEventListener("click", closeSettings);
    if (sm) {
      sm.addEventListener("click", (e) => {
        if (e && e.target === sm) closeSettings();
      });
    }

    $("apiBase").addEventListener("change", function () {
      localStorage.setItem(LS.api, String(this.value || ""));
      refreshPills();
    });
    $("devKey").addEventListener("change", function () {
      localStorage.setItem(LS.dev, String(this.value || ""));
      refreshPills();
    });
    $("theme").addEventListener("change", function () {
      setTheme(this.value);
    });
    const sfxSel = $("sfx");
    if (sfxSel) {
      sfxSel.value = (localStorage.getItem(LS.sfx) || "on").trim() || "on";
      sfxSel.addEventListener("change", function () {
        localStorage.setItem(LS.sfx, String(this.value || "on"));
        toast(this.value === "off" ? "声效已关闭" : "声效已开启");
      });
    }

    $("btnLogin").addEventListener("click", async () => {
      try {
        await doLogin();
      } catch (e) {
        logEvent({ ok: false, action: "dev-login", error: e });
      }
    });
    $("btnMe").addEventListener("click", async () => {
      try {
        await doMe();
      } catch (e) {
        logEvent({ ok: false, action: "me", error: e });
      }
    });
    $("btnSellAll").addEventListener("click", async () => {
      try {
        setBusy(true);
        await doSellAll2();
      } catch (e) {
        logEvent({ ok: false, action: "sell_all", error: e });
      } finally {
        setBusy(false);
      }
    });
    $("btnCast").addEventListener("click", async () => {
      try {
        setBusy(true);
        await castRod();
      } catch (e) {
        logEvent({ ok: false, action: "cast", error: e });
      } finally {
        setBusy(false);
      }
    });
    $("btnPull").addEventListener("click", async () => {
      try {
        setBusy(true);
        await pullRod();
      } catch (e) {
        // cooldown error etc
        logEvent({ ok: false, action: "pull", error: e });
        // if server says cooldown, sync local cooldown
        const d = e && e.data ? e.data.detail : null;
        if (e && e.status === 429 && d && d.code === "cooldown") {
          startCooldown(Number(d.retry_after_s || 1));
        }
      } finally {
        setBusy(false);
      }
    });
    $("bobber").addEventListener("click", () => {
      if (phase === "bite") $("btnPull").click();
      else $("btnCast").click();
    });
    $("btnClear").addEventListener("click", () => {
      setToken("");
      refreshPills();
      logEvent({ ok: true, action: "clear_token" });
      clearBiteTimer();
      setBite(false);
      setPhase("idle", "点击「抛竿」开始");
    });

    // Area buttons: switch UI theme now; backend spot switching can be added later
    const setAreaOn = (id) => {
      const ids = ["areaPond", "areaLake", "areaSea"];
      for (const x of ids) {
        const el = $(x);
        if (el) el.classList.toggle("on", x === id);
      }
    };
    const setAreaTheme = (area) => {
      const g = $("gameBox");
      const w = $("water");
      if (g) {
        g.classList.remove("game-pond", "game-lake", "game-sea");
        g.classList.add(`game-${area}`);
      }
      if (w) {
        w.classList.remove("water-pond", "water-lake", "water-sea");
        w.classList.add(`water-${area}`);
      }
    };
    const areaMsg = () => toast("钓场切换：视觉已切换；后端真源接口后续再接");
    const ap = $("areaPond");
    const al = $("areaLake");
    const as = $("areaSea");
    if (ap) ap.addEventListener("click", () => { setAreaOn("areaPond"); setAreaTheme("pond"); areaMsg(); });
    if (al) al.addEventListener("click", () => { setAreaOn("areaLake"); setAreaTheme("lake"); areaMsg(); });
    if (as) as.addEventListener("click", () => { setAreaOn("areaSea"); setAreaTheme("sea"); areaMsg(); });
  };

  document.addEventListener("DOMContentLoaded", () => {
    setTheme(localStorage.getItem(LS.theme) || "calm");
    document.documentElement.setAttribute("data-view", "first");
    syncInputs();
    wire();
    logEvent("Ready.（若看到 401 未登录，先点 dev-login）");
    setPhase("idle", "点击「抛竿」开始");
    initFishShadows();
    startSceneLoop();
    window.addEventListener("resize", () => {
      updateRodAndLine();
    });
    setBobberPos(50, 54);
    // best effort: load state if already logged-in
    if (getToken()) {
      doMe().catch(() => {});
    } else {
      renderInventory({});
      tickCooldown();
    }
  });
})();
