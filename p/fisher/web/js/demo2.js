(() => {
  const $ = (id) => document.getElementById(id);

  // DOM
  const tip = $("tip");
  const coin = $("coin");
  const score = $("score");
  const rodBox = $("rodBox");
  const float = $("float");
  const wave = $("wave");
  const hook = $("hook");
  const lineSvg = $("lineSvg");
  const linePath = $("linePath");
  const linePathUnder = $("linePathUnder");
  const fishTip = $("fishTip");
  const surpriseTip = $("surpriseTip");
  const castBtn = $("castBtn");
  const pullBtn = $("pullBtn");
  const storage = $("storage");
  const gameBox = $("gameBox");
  const waterBox = $("waterBox");
  const fishShadows = $("fishShadows");
  const sceneDecor = $("sceneDecor");
  const calendar = $("calendar");
  const nightMask = $("nightMask");
  const fogBox = $("fogBox");
  const snowBox = $("snowBox");
  const torch = $("torch");
  const rainBox = $("rainBox");
  const lightning = $("lightning");
  const areaMask = $("areaMask");
  const areaList = $("areaList");

  // Masks
  const ageMask = $("ageMask");
  const roleMask = $("roleMask");
  const helpMask = $("helpMask");
  const shopMask = $("shopMask");

  // Buttons
  const btnAgeOk = $("btnAgeOk");
  const btnRoleOk = $("btnRoleOk");
  const btnHelpOk = $("btnHelpOk");
  const btnShopClose = $("btnShopClose");
  const btnHelp = $("btnHelp");
  const btnShop = $("btnShop");
  const btnBag = $("btnBag");
  const btnArea = $("btnArea");
  const btnAreaClose = $("btnAreaClose");
  const btnGoal = $("btnGoal");
  const btnSys = $("btnSys");
  const roleBadge = $("roleBadge");
  const roleIcon = $("roleIcon");
  const roleName = $("roleName");
  const splash2 = $("splash2");
  const spotlight = $("spotlight");
  const tooltip = $("tooltip");
  const fightHud = $("fightHud");
  const fightFill = $("fightFill");
  const fightTxt = $("fightTxt");

  // Config
  const ageRoles = {
    kid: [{ icon: "🐨", txt: "考拉" }, { icon: "🐰", txt: "兔兔" }, { icon: "🐼", txt: "熊猫" }],
    young: [{ icon: "👨‍🌾", txt: "渔隐" }, { icon: "👩‍🌾", txt: "渔女" }, { icon: "🧑‍🎤", txt: "渔青" }],
    old: [{ icon: "👴", txt: "渔翁" }, { icon: "🧓", txt: "渔伯" }, { icon: "👵", txt: "渔婆" }],
  };

  const areaStyle = {
    pond: {
      game: "game-pond",
      water: "water-pond",
      shadow: `<div class="fishShadow fs-pond-1"></div><div class="fishShadow fs-pond-2"></div>`,
      decor: `<div class="scene-decor plant pond-grass"></div><div class="scene-decor pond-flower"></div>`,
    },
    lake: {
      game: "game-lake",
      water: "water-lake",
      shadow: `<div class="fishShadow fs-lake-1"></div><div class="fishShadow fs-lake-2"></div>`,
      decor: `<div class="scene-decor lake-lotus"></div>`,
    },
    sea: {
      game: "game-sea",
      water: "water-sea",
      shadow: `<div class="fishShadow fs-sea-1"></div><div class="fishShadow fs-sea-2"></div>`,
      decor: `<div class="scene-decor sea-coral"></div><div class="scene-decor sea-shell"></div>`,
    },
  };

  // Fish roles (our local SVG icons; ids map to /assets/fish/<id>.svg)
  const fishData = {
    pond: [
      { id: 2, name: "小鲫鱼", coin: 12 },
      { id: 4, name: "小鲤鱼", coin: 18 },
      { id: 3, name: "麦穗鱼", coin: 10 },
    ],
    lake: [
      { id: 6, name: "草鱼", coin: 35 },
      { id: 7, name: "青鱼", coin: 48 },
      { id: 10, name: "巨型鲤鱼", coin: 68 },
    ],
    sea: [
      { id: 11, name: "小黄鱼", coin: 24 },
      { id: 14, name: "鲷鱼", coin: 72 },
      { id: 15, name: "变异浅海巨鱼", coin: 160 },
    ],
  };

  // State
  let coinNum = 200;
  let scoreNum = 0;
  let canPull = false;
  let curArea = "pond";
  let curAge = "young";
  let fishBag = {}; // key: fish name -> {num,id,coin}
  let items = { torch: false, float: false, raincoat: false, bait: false, hook: false };
  let isNight = false;
  let weather = "sunny";
  let surpriseTimer = null;
  let unlockedAreas = { pond: true };
  let pendingFish = null; // decided at bite-time, consumed at pull
  let lastHookPt = null; // {x,y} in scene coords
  let hookNearEl = null;
  let fishPhase = "idle"; // idle -> waiting -> bite -> fight
  let fightUntilTs = 0;
  let fightMeter01 = 0;
  let lastFightTapAt = 0;
  let tapRateEma = 0; // taps per second (EMA)
  let biteUntilTs = 0; // must yank before this or fish may run
  let nextBubbleAt = 0;
  let bubbleBurstLeft = 0;
  let nextNearFishAt = 0;
  let nearShadowOnUntil = 0;
  let nextNearShadowAt = 0;
  let baitEl = null;
  // Luck system (placeholder for spend/time/referral later)
  let stats = {
    startedAtMs: Date.now(),
    playSeconds: 0,
    spentCoin: 0,
    referralCount: 0,
  };
  // 首期：不做玩家市场；只做系统回收价（保底回收）

  // Sys settings (persist)
  const LS = {
    sfx: "ai24x_demo2_sfx",
    motion: "ai24x_demo2_motion",
    vibrate: "ai24x_demo2_vibrate",
    night: "ai24x_demo2_night",
    state: "ai24x_fisher_demo2_state_v1",
  };
  const sysMask = $("sysMask");
  const optSfx = $("optSfx");
  const optMotion = $("optMotion");
  const optVibrate = $("optVibrate");
  const optNight = $("optNight");
  const btnSysClose = $("btnSysClose");

  const setText = (el, s) => { if (el) el.textContent = String(s); };

  const setFightHud = (on, meter01 = 0, text = "") => {
    if (!fightHud || !fightFill || !fightTxt) return;
    fightHud.classList.toggle("on", !!on);
    const pct = Math.max(0, Math.min(1, Number(meter01 || 0))) * 100;
    fightFill.style.width = `${pct.toFixed(1)}%`;
    if (text) fightTxt.textContent = String(text);
  };

  const recyclePriceOf = (base) => Math.max(1, Math.floor(Math.max(1, Number(base || 1)) * 0.8));

  const saveState = () => {
    try {
      localStorage.setItem(LS.state, JSON.stringify({ coinNum, scoreNum, fishBag, items, curArea, curAge, unlockedAreas, stats }));
    } catch {}
  };
  const loadState = () => {
    try {
      const raw = localStorage.getItem(LS.state);
      if (!raw) return;
      const s = JSON.parse(raw);
      if (Number.isFinite(Number(s.coinNum))) coinNum = Number(s.coinNum);
      if (Number.isFinite(Number(s.scoreNum))) scoreNum = Number(s.scoreNum);
      if (s.fishBag && typeof s.fishBag === "object") fishBag = s.fishBag;
      if (s.items && typeof s.items === "object") items = { ...items, ...s.items };
      if (typeof s.curArea === "string") curArea = s.curArea;
      if (typeof s.curAge === "string") curAge = s.curAge;
      if (s.unlockedAreas && typeof s.unlockedAreas === "object") unlockedAreas = { pond: true, ...s.unlockedAreas };
      if (s.stats && typeof s.stats === "object") {
        stats = {
          startedAtMs: Number(s.stats.startedAtMs || Date.now()),
          playSeconds: Number(s.stats.playSeconds || 0),
          spentCoin: Number(s.stats.spentCoin || 0),
          referralCount: Number(s.stats.referralCount || 0),
        };
      }
    } catch {}
  };

  const _clamp01 = (x) => Math.max(0, Math.min(1, Number(x || 0)));

  const getLuck01 = () => {
    // 0.9 ~ 1.12 typical range; can be tied to spend/time/referral later
    const t = _clamp01((stats.playSeconds || 0) / (60 * 25));     // 0..1 over ~25min
    const s = _clamp01((stats.spentCoin || 0) / 2600);            // 0..1 over some spend
    const r = _clamp01((stats.referralCount || 0) / 10);          // 0..1 over 10 refs
    const base = 0.96 + t * 0.06 + s * 0.06 + r * 0.04;
    // small per-attempt jitter (fortune)
    const jitter = (Math.random() * 2 - 1) * 0.04;
    return Math.max(0.88, Math.min(1.16, base + jitter));
  };

  const areas = [
    { id: "pond", name: "小池塘", unlockCoin: 0, desc: "新手练手 · 平静水面" },
    { id: "lake", name: "湖泊", unlockCoin: 600, desc: "更多鱼种 · 风浪略大" },
    { id: "sea", name: "深海", unlockCoin: 1800, desc: "稀有大鱼 · 更刺激" },
  ];

  const play = (name) => {
    try {
      const s = window.SFX;
      if (!s) return;
      if (typeof s[name] === "function") s[name]();
    } catch {}
  };

  const setTooltip = (html, x, y) => {
    if (!tooltip) return;
    if (!html) {
      tooltip.classList.remove("on");
      return;
    }
    tooltip.innerHTML = html;
    const pad = 12;
    const w = tooltip.offsetWidth || 240;
    const h = tooltip.offsetHeight || 80;
    const xx = Math.max(pad, Math.min(window.innerWidth - w - pad, Number(x || 0) + 12));
    const yy = Math.max(pad, Math.min(window.innerHeight - h - pad, Number(y || 0) + 12));
    tooltip.style.left = `${xx}px`;
    tooltip.style.top = `${yy}px`;
    tooltip.classList.add("on");
  };

  const getOpt = (k, def = "on") => (localStorage.getItem(k) || def).trim();
  const setOpt = (k, v) => localStorage.setItem(k, v ? "on" : "off");

  const applySys = () => {
    const sfxOn = getOpt(LS.sfx, "on") !== "off";
    const motionOn = getOpt(LS.motion, "on") !== "off";
    const vibOn = getOpt(LS.vibrate, "on") !== "off";
    const nightOn = getOpt(LS.night, "on") !== "off";
    if (optSfx) optSfx.checked = sfxOn;
    if (optMotion) optMotion.checked = motionOn;
    if (optVibrate) optVibrate.checked = vibOn;
    if (optNight) optNight.checked = nightOn;
    if (window.SFX && typeof window.SFX.setEnabled === "function") window.SFX.setEnabled(sfxOn);
    document.documentElement.classList.toggle("reduced-motion", !motionOn);
    if (!nightOn && isNight) {
      // force back to day immediately
      isNight = false;
      nightMask && (nightMask.style.display = "none");
      document.body.classList.remove("night");
      gameBox && gameBox.classList.remove("night");
      const sun = document.querySelector(".sun");
      const moon = document.querySelector(".moon");
      if (sun) sun.style.display = "block";
      if (moon) moon.style.display = "none";
    }
  };

  // Age / Role
  const buildRoleGrid = () => {
    const g = $("roleGrid");
    if (!g) return;
    g.innerHTML = "";
    ageRoles[curAge].forEach((r, i) => {
      const div = document.createElement("div");
      div.className = "roleItem" + (i === 0 ? " active" : "");
      div.addEventListener("click", () => {
        g.querySelectorAll(".roleItem").forEach((e) => e.classList.remove("active"));
        div.classList.add("active");
      });
      div.innerHTML = `<div class="roleIcon">${r.icon}</div><div class="roleText">${r.txt}</div>`;
      g.appendChild(div);
    });
  };

  const selectAge = (type, el) => {
    curAge = type;
    document.querySelectorAll(".ageItem").forEach((i) => i.classList.remove("active"));
    if (el) el.classList.add("active");
    gameBox.className = gameBox.className.replace(/style-\w+/g, `style-${type}`);
    document.body.className = document.body.className.replace(/style-\w+/g, `style-${type}`) || `style-${type}`;
    buildRoleGrid();
    saveState();
  };

  const setRoleBadge = () => {
    // read active role item in role grid
    const active = document.querySelector("#roleGrid .roleItem.active");
    const icon = active ? active.querySelector(".roleIcon")?.textContent : "👨‍🌾";
    const name = active ? active.querySelector(".roleText")?.textContent : "渔隐";
    if (roleIcon) roleIcon.textContent = String(icon || "👨‍🌾");
    if (roleName) roleName.textContent = String(name || "渔隐");
    if (roleBadge) roleBadge.style.display = "flex";
  };

  // Weather / night
  const changeWeather = (w) => {
    weather = w;
    if (rainBox) rainBox.innerHTML = "";
    if (lightning) lightning.classList.remove("active");
    if (fogBox) fogBox.classList.remove("on");
    if (snowBox) { snowBox.innerHTML = ""; snowBox.style.display = "none"; }
    // sky elements: keep slow, add slight randomness each switch
    document.querySelectorAll(".cloud").forEach((c) => {
      const dur = 78 + Math.random() * 68; // very slow
      c.style.animationDuration = `${dur.toFixed(1)}s, ${Math.max(14, 18 + Math.random() * 8).toFixed(1)}s`;
      c.style.animationDelay = `${(-Math.random() * dur).toFixed(1)}s, ${(-Math.random() * 8).toFixed(1)}s`;
      c.style.opacity = (0.78 + Math.random() * 0.16).toFixed(2);
    });
    const sun = document.querySelector(".sun");
    const moon = document.querySelector(".moon");
    if (sun) sun.style.animationDuration = `${18 + Math.random() * 18}s`;
    if (moon) moon.style.animationDuration = `${20 + Math.random() * 20}s`;

    if (w === "rain") {
      setText(calendar, "山河日历 · 雨天");
      for (let i = 0; i < 20; i++) {
        const d = document.createElement("div");
        d.className = "raindrop";
        d.style.left = Math.random() * 100 + "%";
        d.style.top = Math.random() * 100 + "%";
        rainBox && rainBox.appendChild(d);
      }
      return;
    }
    if (w === "storm") {
      setText(calendar, "山河日历 · 雷暴雨");
      lightning && lightning.classList.add("active");
      play("thunder");
      return;
    }
    if (w === "fog") {
      setText(calendar, "山河日历 · 起雾");
      if (fogBox) fogBox.classList.add("on");
      document.querySelectorAll(".cloud").forEach((c) => { c.style.opacity = ".62"; });
      return;
    }
    if (w === "snow") {
      setText(calendar, "山河日历 · 小雪");
      if (snowBox) {
        snowBox.style.display = "block";
        const n = Math.max(14, Math.min(28, Math.round(window.innerWidth / 18)));
        for (let i = 0; i < n; i++) {
          const f = document.createElement("div");
          f.className = "snowflake";
          f.style.left = (Math.random() * 100).toFixed(2) + "%";
          f.style.top = (Math.random() * 30).toFixed(2) + "%";
          f.style.animationDelay = (-Math.random() * 3.2).toFixed(2) + "s";
          f.style.animationDuration = (2.6 + Math.random() * 2.4).toFixed(2) + "s";
          f.style.opacity = (0.25 + Math.random() * 0.55).toFixed(2);
          const s = (4 + Math.random() * 5).toFixed(2);
          f.style.width = s + "px";
          f.style.height = s + "px";
          snowBox.appendChild(f);
        }
      }
      document.querySelectorAll(".cloud").forEach((c) => { c.style.opacity = ".84"; });
      return;
    }
    if (w === "windy") {
      setText(calendar, "山河日历 · 大风");
      document.querySelectorAll(".cloud").forEach((c, idx) => {
        const dur = idx % 2 === 0 ? 38 : 46;
        c.style.animationDuration = `${dur}s, ${Math.max(12, 16 + Math.random() * 6).toFixed(1)}s`;
        c.style.opacity = ".92";
      });
      return;
    }
    if (w === "sunset") { setText(calendar, "山河日历 · 日落"); return; }
    setText(calendar, "山河日历 · 晴天");
  };

  const toggleNight = () => {
    const nightOn = getOpt(LS.night, "on") !== "off";
    if (!nightOn) return;
    isNight = !isNight;
    if (nightMask) {
      nightMask.style.display = isNight ? "block" : "none";
      nightMask.style.animation = isNight ? "nightFade 2.2s forwards" : "";
      // darken both sky + water (mask is fixed fullscreen in CSS)
    }
    document.body.classList.toggle("night", isNight);
    gameBox && gameBox.classList.toggle("night", isNight);
    if (torch) torch.style.display = isNight && items.torch ? "block" : "none";
    const sun = document.querySelector(".sun");
    const moon = document.querySelector(".moon");
    if (sun) sun.style.display = isNight ? "none" : "block";
    if (moon) moon.style.display = isNight ? "block" : "none";
    saveState();
  };

  const setSpotlight = (on) => {
    if (!spotlight) return;
    spotlight.classList.toggle("on", !!on);
  };

  const updateLine = () => {
    if (!lineSvg || !linePath || !rodBox || !float) return;
    const shown = float.classList.contains("floatShow");
    if (!shown) {
      lineSvg.style.display = "none";
      if (hookNearEl) hookNearEl.classList.remove("on");
      if (hook) hook.style.opacity = "0";
      if (linePathUnder) linePathUnder.setAttribute("d", "");
      return;
    }
    lineSvg.style.display = "block";

    const sc = document.querySelector(".scene");
    const sr = sc && sc.getBoundingClientRect ? sc.getBoundingClientRect() : null;
    if (!sr) return;
    // Important: match SVG coordinate space to scene pixels
    lineSvg.setAttribute("viewBox", `0 0 ${Math.max(1, sr.width)} ${Math.max(1, sr.height)}`);

    const rr = rodBox.getBoundingClientRect();
    const seg3 = rodBox.querySelector ? rodBox.querySelector(".seg3") : null;
    const tr = seg3 && seg3.getBoundingClientRect ? seg3.getBoundingClientRect() : null;
    const fr = float.getBoundingClientRect();

    // Rod tip: base at seg3 top-center-ish; when fish is on (pull), bias to right-top to "stick" to bamboo tip.
    const pull01 = (fishPhase === "fight" || canPull) ? 1 : 0;
    const biasX = pull01 ? 4 : 0;
    const biasY = pull01 ? -2 : 0;
    const tipPct = pull01 ? 0.64 : 0.52;
    const x1 = ((tr ? (tr.left + tr.width * tipPct) : (rr.left + rr.width * 0.56)) - sr.left) + biasX;
    const y1 = ((tr ? (tr.top + tr.height * 0.03) : (rr.top + rr.height * 0.03)) - sr.top) + biasY;

    // Float center (slightly above mid for half-submerged illusion)
    const x2 = (fr.left + fr.width * 0.50) - sr.left;
    const y2 = (fr.top + fr.height * 0.45) - sr.top;
    // Hook point: deeper underwater so it's not "stuck to float"
    const depth = curArea === "sea" ? 156 : (curArea === "lake" ? 140 : 124);
    const hx = x2 + (canPull ? 2 : 1); // slight offset to avoid perfectly overlapping line
    const hy = y2 + depth;
    lastHookPt = { x: hx, y: hy };

    // Hook visual: keep hook near the line end (more "real")
    if (hook) {
      if (shown) {
        const shopOpen = !!(shopMask && shopMask.style.display === "flex");
        // In water: blurred and faint; only clear when selecting/changing gear
        hook.style.filter = shopOpen ? "drop-shadow(0 2px 6px rgba(0,0,0,.12))" : "blur(1.15px) drop-shadow(0 2px 6px rgba(0,0,0,.10))";
        hook.style.opacity = shopOpen ? "0.92" : (items.hook ? "0.38" : "0.26");
        hook.style.left = `${hx.toFixed(1)}px`;
        hook.style.top = `${hy.toFixed(1)}px`;
        hook.style.transform = "translate(-50%,-50%)";
        hook.classList.toggle("struggle", fishPhase === "bite" || fishPhase === "fight");
      } else {
        hook.style.opacity = "0";
        hook.classList.remove("struggle");
      }
    }

    // Curvature control point: sag a bit, with small wind drift
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dist = Math.max(40, Math.hypot(dx, dy));
    const sag = Math.min(46, Math.max(10, dist * (0.10 + pull01 * 0.06)));
    const wind = weather === "windy" ? 10 : 3;
    const t = Date.now() / 1000;
    const bite01 = (fishPhase === "bite") ? 1 : 0;
    const fight01 = (fishPhase === "fight" || fishPhase === "net") ? 1 : 0;
    const amp = 1 + (fight01 ? (0.8 + fightMeter01 * 1.6) : 0) + bite01 * 0.9;
    const tugX = pull01 ? Math.sin(t * (8.5 + fight01 * 1.6)) * (2.0 * amp) : 0;
    const tugY = pull01 ? Math.cos(t * (10.5 + fight01 * 2.0)) * (1.4 * amp + bite01 * 1.8) : 0;
    const cx = (x1 + x2) / 2 + Math.sin(t * 0.9) * wind + tugX;
    const cy = (y1 + y2) / 2 + sag + Math.cos(t * 0.7) * 1.2 + tugY;

    linePath.setAttribute("d", `M ${x1.toFixed(1)} ${y1.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`);

    // Underwater segment: float -> hook (lighter, longer)
    if (linePathUnder) {
      const uSag = Math.min(22, Math.max(8, dist * 0.035)) + (canPull ? 8 : 0);
      const ux = (x2 + hx) / 2 + Math.sin(t * 1.2) * 1.2;
      const uy = (y2 + hy) / 2 + uSag;
      linePathUnder.setAttribute("d", `M ${x2.toFixed(1)} ${y2.toFixed(1)} Q ${ux.toFixed(1)} ${uy.toFixed(1)} ${hx.toFixed(1)} ${hy.toFixed(1)}`);
    }

    // Near-hook faint shadow for anticipation (only when waiting, not yet bitten)
    if (!hookNearEl && sc) {
      hookNearEl = document.createElement("div");
      hookNearEl.className = "hookShadowNear";
      sc.appendChild(hookNearEl);
    }
    if (hookNearEl) {
      const now = Date.now();
      const waiting = (fishPhase === "waiting");
      // make it intermittent: appear after random delay, stay briefly, then disappear
      if (waiting && now > nextNearShadowAt) {
        const showP = 0.33;
        if (Math.random() < showP) {
          nearShadowOnUntil = now + (900 + Math.random() * 1400);
        }
        nextNearShadowAt = now + (1200 + Math.random() * 2600);
      }
      const on = waiting && now < nearShadowOnUntil;
      hookNearEl.classList.toggle("on", on);
      const tt = Date.now() / 1000;
      const dx2 = Math.sin(tt * 0.8) * 18;
      const dy2 = Math.cos(tt * 0.7) * 6;
      hookNearEl.style.left = `${(hx + dx2).toFixed(1)}px`;
      hookNearEl.style.top = `${(hy + 14 + dy2).toFixed(1)}px`;
      hookNearEl.style.transform = "translate(-50%,-50%)";
    }

    // Bait visual near hook (only if bait bought)
    if (sc && items.bait) {
      if (!baitEl) {
        baitEl = document.createElement("div");
        baitEl.className = "baitDot";
        sc.appendChild(baitEl);
      }
      baitEl.style.left = `${(hx + 3).toFixed(1)}px`;
      baitEl.style.top = `${(hy + 8).toFixed(1)}px`;
      baitEl.style.opacity = (fishPhase === "fight" || fishPhase === "bite") ? "0.25" : "0.45";
    } else if (baitEl) {
      baitEl.remove();
      baitEl = null;
    }
  };

  const spawnHookBubble = () => {
    try {
      const sc = document.querySelector(".scene");
      if (!sc || !lastHookPt) return;
      // only when float is on water; bubbles mostly when waiting
      if (!float || !float.classList.contains("floatShow")) return;
      if (canPull && Math.random() < 0.65) return; // reduce when already bitten

      const b = document.createElement("div");
      b.className = "hookBubble";
      b.style.left = `${lastHookPt.x.toFixed(1)}px`;
      b.style.top = `${(lastHookPt.y + 10).toFixed(1)}px`;
      b.style.setProperty("--dx", `${(Math.random() * 18 - 9).toFixed(1)}px`);
      b.style.setProperty("--dy", `${(28 + Math.random() * 26).toFixed(1)}px`);
      b.style.width = b.style.height = `${(5 + Math.random() * 6).toFixed(1)}px`;
      sc.appendChild(b);
      setTimeout(() => b.remove(), 1800);
    } catch {}
  };

  const bubbleTick = () => {
    if (!float || !float.classList.contains("floatShow")) return;
    const now = Date.now();
    // not always bubbling; create intermittent bursts
    if (now < nextBubbleAt) return;
    if (bubbleBurstLeft <= 0) {
      // start a burst occasionally (more when waiting, less when fighting)
      const baseGap = fishPhase === "waiting" ? 2400 : (fishPhase === "bite" ? 3200 : 4200);
      nextBubbleAt = now + baseGap + Math.floor(Math.random() * 2200);
      bubbleBurstLeft = (fishPhase === "waiting" && Math.random() < 0.38) ? (1 + Math.floor(Math.random() * 2)) : (Math.random() < 0.12 ? 1 : 0);
      return;
    }
    // emit one bubble in the burst
    spawnHookBubble();
    bubbleBurstLeft -= 1;
    nextBubbleAt = now + 220 + Math.floor(Math.random() * 260);
  };

  const spawnNearHookFish = () => {
    try {
      const sc = document.querySelector(".scene");
      if (!sc || !lastHookPt) return;
      const n = 1 + (Math.random() < 0.35 ? 1 : 0) + (Math.random() < 0.18 ? 1 : 0); // 1~3
      for (let i = 0; i < n; i++) {
        const el = document.createElement("div");
        el.className = "hookFishNear";
        const dir = Math.random() < 0.5 ? -1 : 1;
        const startX = lastHookPt.x + dir * (80 + Math.random() * 60);
        const startY = lastHookPt.y + 18 + (Math.random() * 36 - 18);
        const endX = lastHookPt.x - dir * (60 + Math.random() * 60);
        const endY = startY + (Math.random() * 22 - 11);
        const w = 26 + Math.random() * 26;
        const h = 9 + Math.random() * 10;
        el.style.width = `${w.toFixed(1)}px`;
        el.style.height = `${h.toFixed(1)}px`;
        el.style.left = `${startX.toFixed(1)}px`;
        el.style.top = `${startY.toFixed(1)}px`;
        sc.appendChild(el);
        const dur = 1400 + Math.random() * 1600;
        el.animate(
          [
            { transform: "translate(-50%,-50%) scale(.9)", opacity: 0 },
            { transform: "translate(-50%,-50%) scale(1)", opacity: 0.55, offset: 0.18 },
            { transform: `translate(calc(-50% + ${(endX - startX).toFixed(1)}px), calc(-50% + ${(endY - startY).toFixed(1)}px)) scale(.95)`, opacity: 0.0 },
          ],
          { duration: dur, easing: "ease-in-out", fill: "forwards" },
        ).onfinish = () => el.remove();
      }
    } catch {}
  };

  const spawnSurfaceFishPreview = (fish) => {
    try {
      const sc = document.querySelector(".scene");
      if (!sc || !lastHookPt || !fish) return;
      const s = document.createElement("div");
      s.className = "surfaceFish";
      s.style.left = `${lastHookPt.x.toFixed(1)}px`;
      s.style.top = `${(lastHookPt.y - 18).toFixed(1)}px`;
      s.innerHTML = `<img alt="${fish.name}" src="${fishIconSrc(fish.id)}" />`;
      sc.appendChild(s);

      // Hook ghost: makes it look like fish is on hook while flopping
      const hg = document.createElement("div");
      hg.className = "hookGhost";
      hg.textContent = "🪝";
      hg.style.left = `${lastHookPt.x.toFixed(1)}px`;
      hg.style.top = `${(lastHookPt.y - 6).toFixed(1)}px`;
      sc.appendChild(hg);

      // Find a near-surface target y: a bit below float (waterline area)
      const fr = float && float.getBoundingClientRect ? float.getBoundingClientRect() : null;
      const sr = sc.getBoundingClientRect();
      const ySurf = fr ? (fr.top + fr.height * 0.62 - sr.top) : (lastHookPt.y - 60);
      const dx = (Math.random() * 36 - 18);

      const frames = [
        { transform: "translate(-50%,-50%) scale(.65)", opacity: 0.0, filter: "blur(.6px)" },
        { transform: `translate(calc(-50% + ${dx.toFixed(1)}px), calc(-50% - 74px)) scale(.95) rotate(-12deg)`, opacity: 0.62, offset: 0.22, filter: "blur(.15px)" },
        { transform: `translate(calc(-50% + ${(dx * 0.65).toFixed(1)}px), calc(-50% - 48px)) scale(.92) rotate(10deg)`, opacity: 0.62, offset: 0.44, filter: "blur(.20px)" },
        { transform: `translate(calc(-50% + ${(dx * 0.35).toFixed(1)}px), calc(-50% - 62px)) scale(.90) rotate(-8deg)`, opacity: 0.60, offset: 0.62, filter: "blur(.22px)" },
        { transform: `translate(calc(-50% + ${(dx * 0.55).toFixed(1)}px), calc(-50% + ${(ySurf - lastHookPt.y).toFixed(1)}px)) scale(.78) rotate(8deg)`, opacity: 0.0, filter: "blur(.55px)" },
      ];

      s.animate(
        [
          ...frames
        ],
        { duration: 1280, easing: "cubic-bezier(.2,.88,.2,1)", fill: "forwards" },
      ).onfinish = () => s.remove();

      // hook ghost follows, but can "blink" briefly (simulating water遮挡/翻身)
      const hgFrames = frames.map((f, idx) => {
        const o = typeof f.opacity === "number" ? f.opacity : 0.6;
        const blink = idx === 2 ? 0.15 : 1;
        return { transform: f.transform, opacity: Math.min(0.75, o * blink), filter: "blur(.45px)" };
      });
      hg.animate(hgFrames, { duration: 1280, easing: "cubic-bezier(.2,.88,.2,1)", fill: "forwards" }).onfinish = () => hg.remove();
    } catch {}
  };

  const decideFishAtBite = () => {
    const pool = fishData[curArea] || fishData.pond;
    const roll = Math.random();
    const rareP = items.hook ? 0.10 : 0.06;
    const fish =
      roll < rareP
        ? { id: 15, name: "变异浅海巨鱼", coin: 160 + Math.floor(Math.random() * 80), _rare: true }
        : { ...pool[Math.floor(Math.random() * pool.length)], _rare: false };
    return fish;
  };

  const updateSpotlightPos = () => {
    if (!spotlight || !float) return;
    if (!isNight) return;
    const fr = float.getBoundingClientRect();
    if (!fr) return;
    const x = fr.left + fr.width / 2;
    const y = fr.top + fr.height * 0.55;
    spotlight.style.left = `${x}px`;
    spotlight.style.top = `${y}px`;
  };

  // Area switch
  const setArea = (a) => {
    const id = String(a || "");
    if (!unlockedAreas[id]) {
      // do not switch silently; open menu for unlock
      if (areaMask) areaMask.style.display = "flex";
      renderAreaMenu();
      return;
    }
    curArea = id;
    gameBox.classList.remove("game-pond", "game-lake", "game-sea");
    gameBox.classList.add(areaStyle[a].game);
    waterBox.classList.remove("water-pond", "water-lake", "water-sea");
    waterBox.classList.add(areaStyle[a].water);
    fishShadows.innerHTML = areaStyle[a].shadow;
    sceneDecor.innerHTML = areaStyle[a].decor;
    saveState();
  };

  const renderAreaMenu = () => {
    if (!areaList) return;
    areaList.innerHTML = "";
    areas.forEach((a) => {
      const unlocked = !!unlockedAreas[a.id];
      const on = curArea === a.id;
      const row = document.createElement("div");
      row.className = `areaRow${unlocked ? "" : " locked"}${on ? " on" : ""}`;
      const priceTxt = a.unlockCoin > 0 ? `${a.unlockCoin}金币解锁` : "默认开放";
      const isPending = !unlocked && areaList.dataset.pending === a.id;
      const tag = unlocked ? (on ? "✅ 当前" : "可切换") : (isPending ? "确认解锁？" : `🔒 ${priceTxt}`);
      row.innerHTML = `
        <div class="l">
          <div class="nm">${a.name}</div>
          <div class="sub">${a.desc}</div>
        </div>
        <div class="tag">${tag}</div>
      `;
      row.addEventListener("click", () => {
        if (unlocked) {
          setArea(a.id);
          if (areaMask) areaMask.style.display = "none";
          return;
        }
        const need = Math.max(0, Number(a.unlockCoin || 0));
        if (coinNum < need) return alert("金币不足，先去钓鱼攒金币");
        // In-panel confirm: first click arms, second click confirms
        if (areaList.dataset.pending !== a.id) {
          areaList.dataset.pending = a.id;
          showSurprise(`再次点击确认解锁：${a.name}（${need}金币）`);
          renderAreaMenu();
          return;
        }
        // confirm unlock now
        areaList.dataset.pending = "";
        coinNum -= need;
        stats.spentCoin = Number(stats.spentCoin || 0) + need;
        unlockedAreas[a.id] = true;
        setText(coin, coinNum);
        play("coin");
        showSurprise(`解锁成功：${a.name}`);
        setArea(a.id);
        areaList.dataset.pending = "";
        renderAreaMenu();
        saveState();
      });
      areaList.appendChild(row);
    });
  };

  // Surprise system
  const showSurprise = (txt) => {
    if (!surpriseTip) return;
    surpriseTip.textContent = String(txt || "");
    surpriseTip.classList.add("show");
    setTimeout(() => surpriseTip.classList.remove("show"), 1600);
  };
  const createBubble = () => {
    const b = document.createElement("div");
    b.className = "bubble";
    b.style.left = Math.random() * 60 + 20 + "%";
    b.style.top = Math.random() * 30 + 50 + "%";
    const sc = document.querySelector(".scene");
    sc && sc.appendChild(b);
    setTimeout(() => b.remove(), 3600);
  };
  const startSurprise = () => {
    clearInterval(surpriseTimer);
    surpriseTimer = setInterval(() => {
      if (!canPull) { clearInterval(surpriseTimer); return; }
      const r = Math.random();
      if (r < 0.22) float && float.classList.add("floatSoft");
      if (r < 0.12) createBubble();
      if (r < 0.09) showSurprise("水面轻轻微动...");
      if (r < 0.06) showSurprise("远处水鸟飞过...");
      if (r < 0.04) showSurprise("水草随风摆动...");
    }, 2200);
  };

  const spawnNpc = () => {
    const box = $("npcBox");
    const sc = document.querySelector(".scene");
    if (!box || !sc) return;
    // keep it light
    if (box.childElementCount >= 4) return;
    const npc = document.createElement("div");
    npc.className = "npc";
    const pool = ["🦋", "🐞", "🪲", "🐢", "🐸", "🐦", "🦗", "🐝", "🪱", "🦎"];
    const icon = pool[Math.floor(Math.random() * pool.length)];
    npc.textContent = icon;
    npc.style.left = Math.round(8 + Math.random() * 84) + "%";
    npc.style.top = Math.round(46 + Math.random() * 42) + "%";
    npc.style.animationDuration = (2.4 + Math.random() * 3.2).toFixed(2) + "s";
    npc.style.opacity = (0.75 + Math.random() * 0.20).toFixed(2);
    npc.addEventListener("click", () => {
      // tiny interaction: varied outcomes (mostly cosmetic)
      const r = Math.random();
      if (r < 0.55) {
        const lines = [
          `你轻轻拍了拍 ${icon}，它又飞走了`,
          `${icon} 在水边停了一会儿`,
          `你盯着 ${icon} 看了两秒，心静了`,
          `${icon} 绕了一圈就不见了`,
        ];
        showSurprise(lines[Math.floor(Math.random() * lines.length)]);
        play("coin");
      } else if (r < 0.82) {
        showSurprise(`${icon} 吓了一跳，扑棱一下跑了`);
        play("splash");
      } else {
        // rare: small coin drop
        const gain = 1 + Math.floor(Math.random() * 3);
        coinNum += gain;
        setText(coin, coinNum);
        saveState();
        showSurprise(`${icon} 叼来了一点小东西 +${gain}💰`);
        play("coin");
      }
      npc.remove();
    });
    box.appendChild(npc);
    setTimeout(() => npc.remove(), 9000 + Math.random() * 7000);
  };

  // Inventory rendering (our fish icons)
  const fishIconSrc = (id) => `../assets/fish/${encodeURIComponent(String(id))}.svg`;

  const refreshStorage = () => {
    if (!storage) return;
    storage.innerHTML = "";
    Object.keys(fishBag).forEach((name) => {
      const f = fishBag[name];
      if (!f || f.num <= 0) return;
      const item = document.createElement("div");
      item.className = "fishItem";
      item.dataset.fish = name;
      item.dataset.num = String(f.num);
      item.dataset.base = String(f.coin);
      item.dataset.recycle = String(recyclePriceOf(f.coin));
      item.innerHTML = `<img class="fishIcon" alt="${name}" src="${fishIconSrc(f.id)}" />
        <div class="fishText">${name}\n${f.num}条</div>`;
      storage.appendChild(item);
    });
  };

  const buyItem = (name, price) => {
    const p = Math.max(0, Number(price || 0));
    if (coinNum < p) return alert("金币不足");
    if (name === "hook" && items.hook) return alert("你已经有锋利钩了");
    coinNum -= p;
    stats.spentCoin = Number(stats.spentCoin || 0) + p;
    items[name] = true;
    setText(coin, coinNum);
    alert("购买成功！");
    if (name === "torch" && torch) torch.style.display = isNight ? "block" : "none";
    saveState();
  };

  // Gameplay
  const startBite = () => {
    // lock fish identity at bite moment
    pendingFish = decideFishAtBite();
    fishPhase = "bite";
    canPull = true;
    // bite window: rare fish more sensitive; sharp hook helps a bit
    const baseMs = pendingFish && pendingFish._rare ? 1300 : 1650;
    const hookBonus = items.hook ? 260 : 0;
    biteUntilTs = Date.now() + baseMs + hookBonus + Math.floor(Math.random() * 260);
    float && float.classList.add("floatBite");
    rodBox && rodBox.classList.add("rodPull");
    play("bite");
    setText(tip, "⚡ 有口！先【扬竿】刺鱼！");
    if (pullBtn) pullBtn.textContent = "扬竿";
    pullBtn && pullBtn.classList.add("show");
    const vibOn = getOpt(LS.vibrate, "on") !== "off";
    if (vibOn && navigator.vibrate) navigator.vibrate(180);
  };

  const cast = () => {
    if (!castBtn || castBtn.disabled) return;
    castBtn.disabled = true;
    pullBtn && pullBtn.classList.remove("show");
    canPull = false;
    pendingFish = null;
    fishPhase = "waiting";
    fightUntilTs = 0;
    fightMeter01 = 0;
    lastFightTapAt = 0;
    tapRateEma = 0;
    biteUntilTs = 0;
    setFightHud(false, 0, "");
    fishTip && fishTip.classList.remove("show");
    if (float) float.className = "float";
    if (rodBox) rodBox.className = "rodBox";

    rodBox && rodBox.classList.add("rodCast");
    play("cast");
    setText(tip, "鱼钩抛出...");

    setTimeout(() => {
      rodBox && rodBox.classList.remove("rodCast");
      hook && hook.classList.add("hookAct");
      play("splash");
      if (splash2) {
        splash2.classList.remove("on");
        // force reflow
        void splash2.offsetWidth;
        splash2.classList.add("on");
      }
    }, 320);

    setTimeout(() => {
      hook && hook.classList.remove("hookAct");
      float && float.classList.add("floatShow");
      wave && wave.classList.add("waveAct");
      setText(tip, "静待鱼讯...（真实钓鱼，耐心等待）");
      startSurprise();
    }, 520);

    const base = 12000 + Math.random() * 13000;
    const baitBoost = items.bait ? 0.78 : 1.0;
    setTimeout(startBite, Math.floor(base * baitBoost));
  };

  const pull = () => {
    if (!canPull) return;
    clearInterval(surpriseTimer);
    // Capture float position BEFORE hiding it (so fly-fish starts from line end, not "from sky")
    const floatRect = float && float.getBoundingClientRect ? float.getBoundingClientRect() : null;

    const fish = pendingFish || decideFishAtBite();
    // Step A: 扬竿刺鱼（set hook）
    if (fishPhase === "bite") {
      const setOkP = Math.max(0.62, (fish._rare ? 0.72 : 0.78) + (items.hook ? 0.08 : 0));
      if (Math.random() > setOkP) {
        // miss -> escape
        canPull = false;
        pendingFish = null;
        fishPhase = "waiting";
        play("splash");
        showSurprise("扬竿慢了…脱钩跑了");
        if (fishTip) {
          fishTip.textContent = "脱钩了！";
          fishTip.classList.add("show");
        }
        wave && wave.classList.add("waveAct");
        pullBtn && pullBtn.classList.remove("show");
        if (float) float.className = "float";
        if (rodBox) rodBox.className = "rodBox";
        setTimeout(() => {
          fishTip && fishTip.classList.remove("show");
          float && float.classList.remove("floatShow");
          wave && wave.classList.remove("waveAct");
          setText(tip, "鱼跑了…再抛一竿！");
          castBtn.disabled = false;
        }, 1050);
        return;
      }
      // hooked -> fight window
      fishPhase = "fight";
      canPull = true;
      play("catch");
      setText(tip, "遛鱼中…连续点【扬竿】顶住，中了才能【抄网】！");
      if (pullBtn) pullBtn.textContent = "扬竿";
      fightUntilTs = Date.now() + (fish._rare ? 5200 : 4200);
      fightMeter01 = 0;
      lastFightTapAt = Date.now();
      tapRateEma = 0;
      setFightHud(true, 0, "遛鱼");
      pendingFish = fish;
      // Cool yank action: lift rod + float a bit, show near-surface struggle preview
      if (rodBox) {
        rodBox.classList.remove("rodYank");
        void rodBox.offsetWidth;
        rodBox.classList.add("rodYank");
      }
      if (float) {
        float.classList.remove("floatYank");
        void float.offsetWidth;
        float.classList.add("floatYank");
      }
      spawnSurfaceFishPreview(fish);
      return;
    }

    // Step B: 遛鱼阶段（需要连续点扬竿，成功后才能抄网）
    if (fishPhase === "fight") {
      const now = Date.now();
      const dt = Math.max(0, now - (lastFightTapAt || now));
      // decay meter if player pauses (harder at higher meter)
      // later stage requires "keep spamming" or progress will slip fast
      const decayMs = 2300 - fightMeter01 * 1200; // 2300ms -> 1100ms
      fightMeter01 = Math.max(0, fightMeter01 - dt / Math.max(900, decayMs));
      lastFightTapAt = now;

      // tap-rate EMA (taps/sec)
      const instRate = dt > 20 ? (1000 / dt) : 0;
      tapRateEma = tapRateEma * 0.84 + instRate * 0.16;

      // required tap speed increases as meter grows (late stage =拼手速)
      const needLo = fish._rare ? 3.6 : 3.2;
      const needHi = fish._rare ? 7.2 : 6.4;
      const needRate = needLo + (needHi - needLo) * Math.min(1, Math.max(0, fightMeter01));
      const rate01 = Math.max(0, Math.min(1, tapRateEma / needRate));
      // build progress: early ok, late requires very high rate
      const baseInc = fish._rare ? 0.14 : 0.16;
      const inc = baseInc * (0.35 + 0.95 * Math.pow(rate01, 1.8));
      fightMeter01 = Math.min(1, fightMeter01 + inc + (items.hook ? 0.02 : 0));
      setFightHud(true, fightMeter01, "遛鱼");

      // yank visuals (reverse of cast, stronger bend)
      if (rodBox) {
        rodBox.classList.remove("rodYank");
        void rodBox.offsetWidth;
        rodBox.classList.add("rodYank");
      }
      if (float) {
        float.classList.remove("floatYank");
        void float.offsetWidth;
        float.classList.add("floatYank");
      }
      spawnSurfaceFishPreview(fish);
      play("bite");

      const luck01 = getLuck01();
      // chance to reach "nettable" moment
      // must be late-enough AND fast-enough (prevents "too quick" net)
      const base = fish._rare ? 0.08 : 0.10;
      const ready = fightMeter01 > (fish._rare ? 0.78 : 0.72) && rate01 > 0.62;
      const chance = ready
        ? Math.min(0.85, base + (fightMeter01 - 0.7) * (fish._rare ? 0.90 : 1.05) + rate01 * (fish._rare ? 0.55 : 0.65) + (items.hook ? 0.05 : 0))
        : 0;
      if (Math.random() < chance * luck01) {
        fishPhase = "net";
        canPull = true;
        pendingFish = fish;
        setText(tip, "到水边了！快【抄网】！");
        if (pullBtn) pullBtn.textContent = "抄网";
        // give a short window to net
        fightUntilTs = now + (fish._rare ? 1900 : 1600);
        setFightHud(true, 1, "抄网窗口");
      } else {
        // Player-facing: keep it immersive; progress is shown by the fight bar
        setText(tip, "遛鱼中…拼命扬竿！稳住别停！");
        // possible escape if too long
        if (now > fightUntilTs && Math.random() < (fish._rare ? 0.35 : 0.22)) {
          fishPhase = "waiting";
          canPull = false;
          pendingFish = null;
          fightUntilTs = 0;
          fightMeter01 = 0;
          tapRateEma = 0;
          play("splash");
          showSurprise("鱼一个猛扎…跑了！");
          wave && wave.classList.add("waveAct");
          pullBtn && pullBtn.classList.remove("show");
          if (float) float.className = "float";
          if (rodBox) rodBox.className = "rodBox";
          setTimeout(() => {
            float && float.classList.remove("floatShow");
            wave && wave.classList.remove("waveAct");
            setText(tip, "鱼跑了…再抛一竿！");
            castBtn.disabled = false;
          }, 1050);
        }
      }
      return;
    }

    // Step C: 抄网收鱼（land fish）
    if (fishPhase === "net") {
      const tooLate = Date.now() > fightUntilTs;
      const luck01 = getLuck01();
      const escapedP = Math.max(0.04, (fish._rare ? 0.18 : 0.10) + (tooLate ? 0.22 : 0) - (items.hook ? 0.05 : 0));
      fishPhase = "waiting";
      canPull = false;
      pendingFish = null;
      fightUntilTs = 0;
      fightMeter01 = 0;
      tapRateEma = 0;
      setFightHud(false, 0, "");

      if (Math.random() < escapedP / Math.max(0.75, luck01)) {
        play("splash");
        showSurprise(fish._rare ? "临门一脚…大鱼跑了" : "抄网慢了…跑了");
        wave && wave.classList.add("waveAct");
        pullBtn && pullBtn.classList.remove("show");
        if (float) float.className = "float";
        if (rodBox) rodBox.className = "rodBox";
        setTimeout(() => {
          fishTip && fishTip.classList.remove("show");
          float && float.classList.remove("floatShow");
          wave && wave.classList.remove("waveAct");
          setText(tip, "鱼跑了…再抛一竿！");
          castBtn.disabled = false;
        }, 1100);
        return;
      }

      // success landing: clear visuals
      if (float) float.className = "float";
      if (rodBox) rodBox.className = "rodBox";
      pullBtn && pullBtn.classList.remove("show");
      setFightHud(false, 0, "");
    } else {
      // fallback
      canPull = false;
      pendingFish = null;
      fishPhase = "waiting";
      pullBtn && pullBtn.classList.remove("show");
      return;
    }

    const add = Math.round(fish.coin * (items.hook ? 1.06 : 1.0));
    coinNum += add;
    scoreNum += 1;
    setText(coin, coinNum);
    setText(score, scoreNum);

    if (!fishBag[fish.name]) fishBag[fish.name] = { num: 0, id: fish.id, coin: fish.coin };
    fishBag[fish.name].num += 1;

    if (fishTip) {
      fishTip.textContent = `钓获：${fish.name} +${add}金币`;
      fishTip.classList.add("show");
    }

    // Update storage first so we can target the correct slot by fish type.
    refreshStorage();

    // Visual: fling fish into right storage column slot (from float/line end)
    try {
      const sc = document.querySelector(".scene");
      if (sc && storage && floatRect) {
        const sr = sc.getBoundingClientRect();
        const target = storage.querySelector ? storage.querySelector(`.fishItem[data-fish="${CSS.escape(fish.name)}"]`) : null;
        const tr = (target && target.getBoundingClientRect) ? target.getBoundingClientRect() : storage.getBoundingClientRect();
        const sx = floatRect.left + floatRect.width * 0.5 - sr.left;
        const sy = floatRect.top + floatRect.height * 0.35 - sr.top;
        const ex = tr.left + tr.width * 0.5 - sr.left;
        const ey = tr.top + tr.height * 0.5 - sr.top;

        const ff = document.createElement("div");
        ff.className = "flyFish";
        ff.style.left = `${sx}px`;
        ff.style.top = `${sy}px`;
        ff.innerHTML = `<img alt="${fish.name}" src="${fishIconSrc(fish.id)}" />`;
        sc.appendChild(ff);

        const dx = ex - sx;
        const dy = ey - sy;
        const lift = Math.min(120, Math.max(70, Math.hypot(dx, dy) * 0.22));

        ff.animate(
          [
            { transform: "translate(-50%,-50%) scale(1) rotate(-10deg)", offset: 0 },
            { transform: `translate(calc(-50% + ${dx * 0.55}px), calc(-50% + ${dy * 0.55 - lift}px)) scale(.92) rotate(10deg)`, offset: 0.55 },
            { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(.75) rotate(6deg)`, offset: 1 },
          ],
          { duration: 520, easing: "cubic-bezier(.2,.9,.2,1)", fill: "forwards" },
        ).onfinish = () => {
          ff.classList.add("done");
          setTimeout(() => ff.remove(), 320);
        };
      }
    } catch {}

    saveState();

    play("catch");
    play("coin");

    const sc = document.querySelector(".scene");
    if (sc) {
      const f = document.createElement("div");
      f.className = "coinFly";
      f.innerText = `+${add}💰`;
      sc.appendChild(f);
      setTimeout(() => f.remove(), 1100);
    }

    if (fish._rare) showSurprise("惊喜！水下巨影一闪而过…");

    setTimeout(() => {
      fishTip && fishTip.classList.remove("show");
      float && float.classList.remove("floatShow");
      wave && wave.classList.remove("waveAct");
      setText(tip, "点击抛竿继续钓鱼");
      castBtn.disabled = false;
    }, 1600);
  };

  // UI helpers
  const openMask = (m) => { if (m) m.style.display = "flex"; };
  const closeMask = (m) => { if (m) m.style.display = "none"; };

  const wire = () => {
    // age selection
    document.querySelectorAll(".ageItem").forEach((el) => {
      el.addEventListener("click", () => selectAge(el.dataset.age, el));
    });
    btnAgeOk && btnAgeOk.addEventListener("click", () => { closeMask(ageMask); openMask(roleMask); });
    btnRoleOk && btnRoleOk.addEventListener("click", () => { setRoleBadge(); closeMask(roleMask); openMask(helpMask); });
    btnHelpOk && btnHelpOk.addEventListener("click", () => { closeMask(helpMask); });

    // top nav
    btnHelp && btnHelp.addEventListener("click", () => openMask(helpMask));
    btnShop && btnShop.addEventListener("click", () => openMask(shopMask));
    btnBag && btnBag.addEventListener("click", () => { location.href = "bag.html"; });
    btnArea && btnArea.addEventListener("click", () => { openMask(areaMask); renderAreaMenu(); });
    btnGoal && btnGoal.addEventListener("click", () => alert("🎯 垂钓境界\n1.新手渔夫\n2.垂钓好手\n3.渔林高手\n4.渔界大师\n5.一竿山海\n6.一渔人生"));

    // system settings
    btnSys && btnSys.addEventListener("click", () => sysMask && (sysMask.style.display = "flex"));
    btnSysClose && btnSysClose.addEventListener("click", () => sysMask && (sysMask.style.display = "none"));
    sysMask && sysMask.addEventListener("click", (e) => { if (e && e.target === sysMask) sysMask.style.display = "none"; });
    optSfx && optSfx.addEventListener("change", () => { setOpt(LS.sfx, optSfx.checked); applySys(); });
    optMotion && optMotion.addEventListener("change", () => { setOpt(LS.motion, optMotion.checked); applySys(); });
    optVibrate && optVibrate.addEventListener("change", () => { setOpt(LS.vibrate, optVibrate.checked); applySys(); });
    optNight && optNight.addEventListener("change", () => { setOpt(LS.night, optNight.checked); applySys(); });

    btnShopClose && btnShopClose.addEventListener("click", () => closeMask(shopMask));
    btnAreaClose && btnAreaClose.addEventListener("click", () => closeMask(areaMask));

    // shop buy
    document.querySelectorAll(".shopItem[data-buy]").forEach((el) => {
      el.addEventListener("click", () => buyItem(el.dataset.buy, el.dataset.price));
    });
    // main buttons
    castBtn && castBtn.addEventListener("click", cast);
    pullBtn && pullBtn.addEventListener("click", pull);

    // storage tooltip (desktop hover)
    if (storage) {
      storage.addEventListener("mousemove", (e) => {
        const it = e.target && e.target.closest ? e.target.closest(".fishItem") : null;
        if (!it) return setTooltip("", 0, 0);
        const nm = it.dataset.fish || "";
        const num = it.dataset.num || "0";
        const base = it.dataset.base || "-";
        const recycle = it.dataset.recycle || "-";
        setTooltip(
          `<div class="t">${nm}</div><div class="m">持有：${num} 条</div><div class="m">基准：${base} 金币/条</div><div class="m">系统回收：${recycle} 金币/条</div><div class="m">点击进入仓库可回收</div>`,
          e.clientX,
          e.clientY,
        );
      });
      storage.addEventListener("mouseleave", () => setTooltip("", 0, 0));
      storage.addEventListener("click", (e) => {
        const it = e.target && e.target.closest ? e.target.closest(".fishItem") : null;
        if (!it) return;
        const nm = it.dataset.fish || "";
        const recycle = it.dataset.recycle || "";
        showSurprise(`${nm}（系统回收：${recycle}/条）`);
      });
    }
  };

  const boot = () => {
    loadState();
    buildRoleGrid();
    changeWeather("sunny");
    sceneDecor.innerHTML = areaStyle.pond.decor;
    applySys();
    refreshStorage();
    saveState();

    // weather rotation (reference-like)
    setInterval(() => {
      const list = ["sunny", "windy", "fog", "rain", "storm", "snow", "sunset"];
      changeWeather(list[Math.floor(Math.random() * list.length)]);
    }, 70000);
    setInterval(toggleNight, 140000);

    // init area
    setArea(curArea || "pond");
    setRoleBadge();
    setText(coin, coinNum);
    setText(score, scoreNum);
    setText(tip, "点击抛竿开始钓鱼");

    // spotlight loop (cheap)
    const loop = () => {
      const floatOn = !!(float && float.classList.contains("floatShow"));
      const lightOn = isNight && floatOn; // 夜钓：浮标在水上就自动照亮
      setSpotlight(lightOn);
      if (spotlight) {
        const sp = items.torch ? 1.0 : 0.92; // 无手电也要看得清
        spotlight.style.setProperty("--sp", String(sp));
      }
      if (lightOn) updateSpotlightPos();
      updateLine();
      bubbleTick();

      // If player doesn't yank in time, fish may run (with randomness)
      if (fishPhase === "bite" && canPull && biteUntilTs > 0 && Date.now() > biteUntilTs) {
        const fish = pendingFish;
        const luck01 = getLuck01();
        const baseRunP = fish && fish._rare ? 0.78 : 0.58;
        const runP = Math.max(0.18, Math.min(0.92, baseRunP - (items.hook ? 0.12 : 0) - (luck01 - 1) * 0.18));
        // either run or give a brief grace extension
        if (Math.random() < runP) {
          canPull = false;
          pendingFish = null;
          fishPhase = "waiting";
          biteUntilTs = 0;
          pullBtn && pullBtn.classList.remove("show");
          play("splash");
          showSurprise("你犹豫了一下…鱼跑了");
          wave && wave.classList.add("waveAct");
          setTimeout(() => {
            float && float.classList.remove("floatShow");
            wave && wave.classList.remove("waveAct");
            setText(tip, "鱼跑了…再抛一竿！");
            castBtn && (castBtn.disabled = false);
          }, 950);
        } else {
          // grace: extend a little but make it urgent
          biteUntilTs = Date.now() + 520 + Math.floor(Math.random() * 220);
          setText(tip, "！快扬竿！它要跑了");
        }
      }

      const now = Date.now();
      if (float && float.classList.contains("floatShow") && lastHookPt && now > nextNearFishAt) {
        // faint fish(s) appear occasionally; less frequent during fight (avoid noise)
        const gap = fishPhase === "waiting" ? 3200 : (fishPhase === "bite" ? 4200 : 5600);
        nextNearFishAt = now + gap + Math.floor(Math.random() * 2600);
        const p = fishPhase === "fight" ? 0.16 : (fishPhase === "bite" ? 0.20 : 0.34);
        if (Math.random() < p) spawnNearHookFish();
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);

    // playtime (luck input)
    setInterval(() => {
      stats.playSeconds = Number(stats.playSeconds || 0) + 5;
      saveState();
    }, 5000);

    // ambient NPCs: only when waiting
    setInterval(() => {
      if (canPull) return;
      // If float is on water (casted), add more; otherwise fewer.
      const casted = float && float.classList.contains("floatShow");
      const p = casted ? 0.65 : 0.35;
      if (Math.random() < p) spawnNpc();
    }, 2600);
  };

  wire();
  boot();
})();

