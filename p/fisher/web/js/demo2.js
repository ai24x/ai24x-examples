(() => {
  const $ = (id) => document.getElementById(id);

  // ── Toast & Confirm (replace alert/confirm) ──
  const toastEl = document.getElementById("toast");
  const showToast = (msg, type = "") => {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.className = "toast " + type + " show";
    clearTimeout(toastEl._tid);
    toastEl._tid = setTimeout(() => { toastEl.className = "toast"; }, 2000);
  };
  // 暴露到全局，供 innerHTML 内联 onclick 使用
  window.showToast = showToast;
  const customConfirm = (msg) => new Promise((resolve) => {
    const mask = document.getElementById("confirmMask");
    const msgEl = document.getElementById("confirmMsg");
    const okBtn = document.getElementById("confirmOk");
    const cancelBtn = document.getElementById("confirmCancel");
    if (!mask) return resolve(false);
    msgEl.textContent = msg;
    mask.style.display = "flex";
    const cleanup = (val) => {
      mask.style.display = "none";
      okBtn.onclick = null;
      cancelBtn.onclick = null;
      mask.onclick = null;
      resolve(val);
    };
    okBtn.onclick = () => cleanup(true);
    cancelBtn.onclick = () => cleanup(false);
    mask.onclick = (e) => { if (e.target === mask) cleanup(false); };
  });

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
  const bagMask = $("bagMask");
  const goalMask = $("goalMask");
  const goalContent = $("goalContent");

  // Buttons
  const btnAgeOk = $("btnAgeOk");
  const btnRoleOk = $("btnRoleOk");
  const btnHelpOk = $("btnHelpOk");
  // ── 垂钓境界系统 ──

  const GOAL_TIERS = [
    { name: "新手渔夫", minScore: 0, icon: "🌱", color: "#8B8B8B" },
    { name: "垂钓好手", minScore: 10, icon: "🐟", color: "#5A8A3C" },
    { name: "渔林高手", minScore: 50, icon: "🐠", color: "#1D9E75" },
    { name: "渔界大师", minScore: 200, icon: "🐬", color: "#378ADD" },
    { name: "一竿山海", minScore: 800, icon: "🐉", color: "#7F77DD" },
    { name: "一渔人生", minScore: 3000, icon: "👑", color: "#D85A30" },
  ];

  const getGoalTier = () => {
    const s = scoreNum;
    let tier = GOAL_TIERS[0];
    for (const t of GOAL_TIERS) {
      if (s >= t.minScore) tier = t;
    }
    return tier;
  };

  const renderGoalPanel = () => {
    if (!goalContent) return;
    const cur = getGoalTier();
    const idx = GOAL_TIERS.findIndex(t => t.name === cur.name);
    const next = idx < GOAL_TIERS.length - 1 ? GOAL_TIERS[idx + 1] : null;
    const pct = next ? Math.min(100, Math.round((scoreNum - cur.minScore) / (next.minScore - cur.minScore) * 100)) : 100;

    let html = `<div style="text-align:center;font-size:48px;margin:8px 0">${cur.icon}</div>`;
    html += `<div style="text-align:center;font-size:20px;font-weight:500;color:${cur.color}">${cur.name}</div>`;
    if (next) {
      html += `<div style="text-align:center;font-size:12px;color:#888;margin-top:4px">下一阶：${next.name}（需${next.minScore}阅历，当前${scoreNum}）</div>`;
      html += `<div style="background:#eee;border-radius:8px;height:12px;margin:12px 0;overflow:hidden">`;
      html += `<div style="background:${cur.color};height:100%;width:${pct}%;transition:width .3s"></div></div>`;
      html += `<div style="text-align:center;font-size:11px;color:#888">${pct}%</div>`;
    } else {
      html += `<div style="text-align:center;font-size:13px;color:${cur.color};margin-top:8px">已达最高境界！</div>`;
    }
    html += `<div style="margin-top:12px;font-size:12px;color:#666;text-align:center">`;
    html += `金币：<b>${coinNum}</b> · 鱼竿：<b>Lv.${playerState ? playerState.rod_level : 0}</b> · 钓场：<b>${getAreas().length}</b>个`;
    html += `</div>`;
    goalContent.innerHTML = html;
  };

  const btnDailyClose = $("btnDailyClose");
  btnDailyClose && btnDailyClose.addEventListener("click", () => closeMask(dailyMask));

  // ── 渔场经营面板（含经营 + 装备展示） ──

  let empireTab = "business";

  const renderEmpirePanel = async () => {
    if (!empireContent) return;
    if (empireTab === "showcase") { renderShowcase(); return; }
    // ... rest of business panel rendering
    if (!window.FisherAPI || !apiInitialized) {
      empireContent.innerHTML = "<div class='emptyHint'>API 未连接</div>";
      return;
    }
    let data;
    try {
      data = await window.FisherAPI._get("/v1/fishery/my");
    } catch { empireContent.innerHTML = "<div class='emptyHint'>数据加载失败</div>"; return; }
    const { fisheries, assets, coins } = data;
    const totalIncome = fisheries.reduce((s, f) => s + f.income_per_hour + f.workers.reduce((ws, w) => ws + w.catch_rate, 0), 0);
    const assetBonus = assets.reduce((s, a) => s + a.bonus_pct, 0);

    let html = `<div style="font-size:13px;color:#888;margin-bottom:8px">💰余额 ${coins} · 总时产 ${totalIncome}/h · 资产加成 +${assetBonus}%</div>`;

    // My Fisheries
    html += `<div style="font-weight:500;margin:12px 0 4px">🐟 我的渔场</div>`;
    if (fisheries.length === 0) {
      html += `<div class="emptyHint">还没有渔场，先买一个吧</div>`;
    } else {
      fisheries.forEach(f => {
        html += `<div style="padding:8px;background:#f8fafc;border-radius:8px;margin-bottom:6px">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <b>${f.name}</b> <span style="font-size:12px">Lv.${f.level}</span>
          </div>
          <div style="font-size:12px;color:#666">💰${f.income_per_hour}/h · 🧑‍🏭${f.worker_count}/${f.workers_max}渔工</div>
          <div style="display:flex;gap:6px;margin-top:6px">
            <button class="miniBtn primary" data-upgrade="${f.id}">升级 (${f.upgrade_cost}💰)</button>
            <button class="miniBtn" data-hire="${f.id}">雇工</button>
          </div>`;
        f.workers.forEach(w => {
          html += `<div style="font-size:11px;color:#888;margin-top:2px">  👷 ${w.name} · 技术${w.skill} · 产出${w.catch_rate}/h</div>`;
        });
        html += `</div>`;
      });
    }

    // Buy Fishery
    html += `<div style="font-weight:500;margin:12px 0 4px">🏪 购买渔场</div>`;
    const shopData = await window.FisherAPI._get("/v1/fishery/shop");
    shopData.fisheries.forEach(s => {
      const owned = fisheries.some(f => f.land_type === s.type);
      html += `<div style="padding:6px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center">
        <div><b>${s.name}</b><div style="font-size:11px;color:#888">${s.desc} · 产${s.income}/h · 可雇${s.workers_max}人</div></div>
        ${owned ? '<span style="font-size:12px;color:#4CAF50">✓ 已拥有</span>' : `<button class="miniBtn primary" data-buy-fishery="${s.type}">${s.price}💰</button>`}
      </div>`;
    });

    // My Assets
    html += `<div style="font-weight:500;margin:12px 0 4px">🏗️ 我的资产</div>`;
    if (assets.length === 0) {
      html += `<div class="emptyHint">还没有资产，买个码头开始经营吧</div>`;
    } else {
      assets.forEach(a => {
        html += `<div style="padding:4px;font-size:13px">${a.name} · 加成+${a.bonus_pct}%</div>`;
      });
    }

    // Buy Assets
    html += `<div style="font-weight:500;margin:12px 0 4px">🛒 资产商店</div>`;
    shopData.assets.forEach(a => {
      const owned = assets.some(ast => ast.type === a.type);
      html += `<div style="padding:4px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center">
        <div><b>${a.name}</b><div style="font-size:11px;color:#888">${a.desc} · 收入+${a.bonus}%</div></div>
        ${owned ? '<span style="font-size:12px;color:#4CAF50">✓ 已拥有</span>' : `<button class="miniBtn primary" data-buy-asset="${a.type}">${a.price}💰</button>`}
      </div>`;
    });

    // Collect Income
    if (fisheries.length > 0) {
      html += `<button class="btnOk" id="btnCollect" style="margin-top:12px;background:#4CAF50">💰 收取租金 (约${totalIncome}💰)</button>`;
    }

    empireContent.innerHTML = html;

    // Event delegation
    empireContent.querySelectorAll("[data-upgrade]").forEach(btn => {
      btn.onclick = async () => {
        try {
          const r = await window.FisherAPI._post(`/v1/fishery/upgrade/${btn.dataset.upgrade}`, {});
          coinNum = r.coins; setText(coin, coinNum);
          showToast(`渔场升级至 Lv.${r.level}！`, "success");
          renderEmpirePanel();
        } catch(e) { showToast(e.message, "error"); }
      };
    });
    empireContent.querySelectorAll("[data-hire]").forEach(btn => {
      btn.onclick = async () => {
        try {
          const r = await window.FisherAPI._post(`/v1/fishery/hire/${btn.dataset.hire}`, {});
          coinNum = r.coins; setText(coin, coinNum);
          showToast(`雇佣了 ${r.name}！技术 Lv.${r.skill}`, "success");
          renderEmpirePanel();
        } catch(e) { showToast(e.message, "error"); }
      };
    });
    empireContent.querySelectorAll("[data-buy-fishery]").forEach(btn => {
      btn.onclick = async () => {
        try {
          const r = await window.FisherAPI._post("/v1/fishery/buy", { land_type: btn.dataset.buyFishery });
          coinNum = r.coins; setText(coin, coinNum);
          showToast(`买下渔场：${r.name}！`, "success");
          renderEmpirePanel();
        } catch(e) { showToast(e.message, "error"); }
      };
    });
    empireContent.querySelectorAll("[data-buy-asset]").forEach(btn => {
      btn.onclick = async () => {
        try {
          const r = await window.FisherAPI._post("/v1/fishery/buy-asset", { asset_type: btn.dataset.buyAsset });
          coinNum = r.coins; setText(coin, coinNum);
          showToast(`购入资产：${r.name}！`, "success");
          renderEmpirePanel();
        } catch(e) { showToast(e.message, "error"); }
      };
    });
    const btnCollect = document.getElementById("btnCollect");
    btnCollect && (btnCollect.onclick = async () => {
      try {
        const r = await window.FisherAPI._post("/v1/fishery/collect", {});
        coinNum = r.coins; setText(coin, coinNum);
        scoreNum = r.score; setText(score, scoreNum);
        showToast(`收租 +${r.total_income}💰`, "success");
        renderEmpirePanel();
      } catch(e) { showToast(e.message, "error"); }
    });
  };

  // ── 装备展示柜 ──

  const ROD_STYLES = [
    { lv:0,name:"竹竿",emoji:"🎋",color:"#c0956b",desc:"新手竹竿，手感温润" },
    { lv:1,name:"铁竹竿",emoji:"🎣",color:"#8B8B7A",desc:"加铁箍的竹竿" },
    { lv:2,name:"精铁竿",emoji:"🎣",color:"#7A7A6A",desc:"全铁打造" },
    { lv:3,name:"青铜竿",emoji:"🎣",color:"#5A8A5A",desc:"青铜材质，古朴厚重" },
    { lv:4,name:"秘银竿",emoji:"🎣",color:"#5A8A8A",desc:"秘银锻造，轻如鸿毛" },
    { lv:5,name:"寒铁竿",emoji:"🎣",color:"#4A6A8A",desc:"寒铁所铸，冰冷坚韧" },
    { lv:6,name:"玄冰竿",emoji:"🎣",color:"#3A5A7A",desc:"千年玄冰寒气逼人" },
    { lv:7,name:"紫晶竿",emoji:"🎣",color:"#6A4A8A",desc:"紫晶镶嵌，灵力流转" },
    { lv:8,name:"暗金竿",emoji:"🎣",color:"#8A6A4A",desc:"暗金铸造，稳重厚实" },
    { lv:9,name:"黄金竿",emoji:"🎣",color:"#C0843A",desc:"纯金打造，璀璨夺目" },
    { lv:10,name:"龙纹竿",emoji:"🐉",color:"#D4A020",desc:"龙纹镌刻，传承之器" },
    { lv:11,name:"凤翎竿",emoji:"🦅",color:"#D4AF37",desc:"凤凰翎羽，轻盈如风" },
    { lv:12,name:"星陨竿",emoji:"⭐",color:"#C0A030",desc:"天外陨铁，星辰之力" },
    { lv:13,name:"圣光竿",emoji:"✨",color:"#E8B030",desc:"圣光祝福，纯粹至净" },
    { lv:14,name:"传说竿",emoji:"🔥",color:"#FF6B6B",desc:"传说之器，举世无双" },
    { lv:15,name:"海神竿",emoji:"👑",color:"#FF3B3B",desc:"海神亲赐，统御七海" },
  ];

  const ASSET_PREVIEWS = [
    { type:"dock",name:"木质码头",emoji:"🏗️",color:"#8B6914",desc:"渔获收购价+10%",bg:"#f5e6c8" },
    { type:"boat",name:"小型渔船",emoji:"⛵",color:"#4A90D9",desc:"渔场收入+20%",bg:"#dceefb" },
    { type:"yacht",name:"豪华游艇",emoji:"🛥️",color:"#D4AF37",desc:"收入+40%，解锁专属鱼种",bg:"#fff8e1" },
    { type:"resort",name:"度假村",emoji:"🏖️",color:"#4CAF50",desc:"收入+80%，接待NPC游客",bg:"#e8f5e9" },
    { type:"island",name:"私人海岛",emoji:"🏝️",color:"#E91E63",desc:"终极资产，收入+150%",bg:"#fce4ec" },
  ];

  const renderShowcase = () => {
    if (!empireContent) return;
    const curLv = playerState ? playerState.rod_level : 0;
    let html = `<div style="font-weight:500;margin-bottom:8px">🎣 鱼竿展示柜（当前: Lv.${curLv} ${ROD_STYLES[curLv]?.name||''}）</div>`;
    html += `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:16px">`;
    ROD_STYLES.forEach(r => {
      const owned = r.lv <= curLv;
      const active = r.lv === curLv;
      html += `<div style="background:${owned?r.color+'15':'#fafafa'};border:2px solid ${active?r.color:owned?'#e0e0e0':'#f0f0f0'};border-radius:10px;padding:6px;text-align:center;${!owned?'opacity:.35':''};transition:.2s">
        <div style="font-size:${active?'28':'22'}px">${r.emoji}</div>
        <div style="font-size:10px;font-weight:600;color:${owned?r.color:'#bbb'}">${r.name}</div>
        <div style="font-size:9px;color:${active?r.color:'#aaa'}">${active?'⚡使用中':owned?'已解锁':'🔒 Lv.'+r.lv}</div>
      </div>`;
    });
    html += `</div>`;
    html += `<div style="font-weight:500;margin-bottom:8px">🏗️ 资产画廊</div>`;
    ASSET_PREVIEWS.forEach(a => {
      html += `<div style="background:${a.bg};border-radius:12px;padding:12px;margin-bottom:8px;display:flex;align-items:center;gap:12px">
        <div style="font-size:32px;background:#fff;border-radius:12px;width:50px;height:50px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,.06)">${a.emoji}</div>
        <div style="flex:1"><div style="font-weight:600;font-size:14px">${a.name}</div><div style="font-size:11px;color:#888">${a.desc}</div></div>
      </div>`;
    });
    empireContent.innerHTML = html;
  };

  // Tab switching
  const tabBusiness = document.getElementById("tabBusiness");
  const tabShowcase = document.getElementById("tabShowcase");
  tabBusiness && (tabBusiness.onclick = () => { empireTab = "business"; tabBusiness.classList.add("primary"); tabShowcase && tabShowcase.classList.remove("primary"); renderEmpirePanel(); });
  tabShowcase && (tabShowcase.onclick = () => { empireTab = "showcase"; tabShowcase.classList.add("primary"); tabBusiness && tabBusiness.classList.remove("primary"); renderShowcase(); });

  // ── 鱼市交易面板 ──

  const renderMarketPanel = async () => {
    if (!marketContent || !window.FisherAPI) return;
    let data;
    try { data = await window.FisherAPI._get("/v1/market/orders"); }
    catch { marketContent.innerHTML = "<div class='emptyHint'>数据加载失败</div>"; return; }

    let html = `<div style="font-weight:500;margin-bottom:8px">📋 挂单出售</div>`;
    html += `<div style="display:flex;gap:6px;margin-bottom:12px">
      <select id="mkSpecies" style="flex:1;padding:6px;border-radius:8px;border:1px solid #ddd">`;
    Object.keys(fishBag).forEach(nm => {
      const f = fishBag[nm];
      if (f && f.num > 0) html += `<option value="${nm}">${nm} (${f.num}条)</option>`;
    });
    html += `</select>
      <input id="mkPrice" type="number" min="1" value="10" placeholder="单价" style="width:60px;padding:6px;border-radius:8px;border:1px solid #ddd">
      <input id="mkQty" type="number" min="1" value="1" placeholder="数量" style="width:50px;padding:6px;border-radius:8px;border:1px solid #ddd">
      <button class="miniBtn primary" id="btnMkList">挂单</button>
    </div>`;

    // Active orders
    html += `<div style="font-weight:500;margin:12px 0 4px">🔥 市场行情</div>`;
    if (!data.active || data.active.length === 0) {
      html += `<div class="emptyHint">暂无挂单</div>`;
    } else {
      data.active.forEach(o => {
        html += `<div style="padding:6px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center">
          <div><b>${o.species_name}</b> ×${o.quantity}<br><span style="font-size:11px;color:#888">${o.price_per_unit}💰/条</span></div>
          <button class="miniBtn primary" data-mk-buy="${o.id}">${o.total_price}💰 购买</button>
        </div>`;
      });
    }

    // My orders
    html += `<div style="font-weight:500;margin:12px 0 4px">📋 我的订单</div>`;
    if (!data.my_orders || data.my_orders.length === 0) {
      html += `<div class="emptyHint">暂无订单</div>`;
    } else {
      data.my_orders.forEach(o => {
        html += `<div style="padding:4px;font-size:13px;border-bottom:1px solid #eee;display:flex;justify-content:space-between">
          <span>${o.species_name} ×${o.quantity} @${o.price_per_unit}💰</span>
          <span style="color:${o.status==='active'?'#55a3c9':o.status==='filled'?'#4CAF50':'#888'}">${o.status==='active'?'挂单中':o.status==='filled'?'已成交':'已取消'}</span>
        </div>`;
      });
    }

    marketContent.innerHTML = html;

    // Wire up
    const btnList = document.getElementById("btnMkList");
    btnList && (btnList.onclick = async () => {
      const nm = document.getElementById("mkSpecies")?.value;
      const price = document.getElementById("mkPrice")?.value;
      const qty = document.getElementById("mkQty")?.value;
      if (!nm) return showToast("请选择鱼获", "error");
      try {
        await window.FisherAPI._post("/v1/market/list", { species_name: nm, price_per_unit: Number(price), quantity: Number(qty) });
        // Remove from local fishBag
        const f = fishBag[nm];
        if (f) { f.num -= Number(qty); if (f.num <= 0) delete fishBag[nm]; }
        refreshStorage();
        showToast("挂单成功!", "success");
        renderMarketPanel();
      } catch(e) { showToast(e.message, "error"); }
    });
    marketContent.querySelectorAll("[data-mk-buy]").forEach(btn => {
      btn.onclick = async () => {
        try {
          const r = await window.FisherAPI._post(`/v1/market/buy/${btn.dataset.mkBuy}`, {});
          coinNum = r.coins; setText(coin, coinNum);
          showToast(`买到 ${r.species_name} ×${r.quantity}！`, "success");
          refreshStorage();
          renderMarketPanel();
        } catch(e) { showToast(e.message, "error"); }
      };
    });
  };

  // ── 每日任务系统 ──

  const questKey = () => `fisher_quests_${new Date().toISOString().slice(0,10)}`;
  let dailyQuests = [];
  let questStats = { fishCaught: 0, coinsEarned: 0, rareCaught: 0 };

  const loadQuests = () => {
    try {
      const raw = localStorage.getItem(questKey());
      if (raw) {
        const d = JSON.parse(raw);
        dailyQuests = d.quests || [];
        questStats = d.stats || { fishCaught: 0, coinsEarned: 0, rareCaught: 0 };
        return;
      }
    } catch {}
    // Generate new quests
    const templates = [
      { id: "fish_n", desc: "钓上 {n} 条鱼", target: [5, 8, 12, 20][Math.floor(Math.random()*4)], reward: 30, stat: "fishCaught" },
      { id: "coin_n", desc: "卖出鱼获赚 {n} 金币", target: [60, 100, 180, 300][Math.floor(Math.random()*4)], reward: 50, stat: "coinsEarned" },
      { id: "rare_n", desc: "钓到 {n} 条稀有品质及以上的鱼", target: [1, 2, 3][Math.floor(Math.random()*3)], reward: 80, stat: "rareCaught" },
    ];
    dailyQuests = templates.map(t => ({...t, progress: 0, done: false}));
    questStats = { fishCaught: 0, coinsEarned: 0, rareCaught: 0 };
    saveQuests();
  };

  const saveQuests = () => {
    try { localStorage.setItem(questKey(), JSON.stringify({ quests: dailyQuests, stats: questStats })); } catch {}
  };

  const updateQuest = (stat, delta) => {
    questStats[stat] = (questStats[stat] || 0) + delta;
    dailyQuests.forEach(q => {
      if (!q.done && q.stat === stat) {
        q.progress = Math.min(q.target, questStats[stat]);
        if (q.progress >= q.target) {
          q.done = true;
          coinNum += q.reward;
          setText(coin, coinNum);
          showToast(`任务完成！+${q.reward}💰`, "success");
          saveState();
        }
      }
    });
    saveQuests();
  };

  const renderDailyPanel = () => {
    if (!dailyList) return;
    dailyList.innerHTML = dailyQuests.map(q => {
      const pct = Math.min(100, Math.round(q.progress / q.target * 100));
      const done = q.done ? "✅" : "";
      return `<div style="padding:10px 0;border-bottom:1px solid rgba(0,0,0,.06)">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>${done} ${q.desc.replace("{n}", q.target)}</span>
          <span style="font-size:12px;color:${q.done?'#4CAF50':'#888'}">+${q.reward}💰</span>
        </div>
        <div style="background:#eee;border-radius:6px;height:8px;margin-top:6px;overflow:hidden">
          <div style="background:${q.done?'#4CAF50':'var(--btn,#55a3c9)'};height:100%;width:${pct}%"></div>
        </div>
        <div style="font-size:11px;color:#888;text-align:right">${q.progress}/${q.target}</div>
      </div>`;
    }).join("");
  };

  const btnShopClose = $("btnShopClose");
  const btnUpgradeRod = $("btnUpgradeRod");
  const sysRodLv = $("sysRodLv");
  const sysRodInfo = $("sysRodInfo");
  const rodLv = $("rodLv");
  const btnHelp = $("btnHelp");
  const btnShop = $("btnShop");
  const btnBag = $("btnBag");
  const btnArea = $("btnArea");
  const btnAreaClose = $("btnAreaClose");
  const btnGoal = $("btnGoal");
  const btnDaily = $("btnDaily");
  const dailyMask = $("dailyMask");
  const dailyList = $("dailyList");
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
    kid: [{ icon: "🧒", txt: "小钓手", style: "kid" }, { icon: "🐣", txt: "萌新", style: "kid" }, { icon: "🌟", txt: "小明星", style: "kid" }],
    young: [{ icon: "🧑", txt: "渔隐", style: "young" }, { icon: "👩", txt: "渔女", style: "young" }, { icon: "🤠", txt: "渔青", style: "young" }],
    old: [{ icon: "👨‍🦳", txt: "渔翁", style: "old" }, { icon: "🧓", txt: "渔伯", style: "old" }, { icon: "👵", txt: "渔婆", style: "old" }],
  };

  // Avatar upload support
  const avatarUpload = async () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (file.size > 200 * 1024) { showToast("图片不能超过200KB", "error"); return; }
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          localStorage.setItem("fisher_avatar", ev.target.result);
          updateRoleBadgeFromAvatar();
          showToast("头像已更新!", "success");
        } catch { showToast("图片太大，请用更小的图", "error"); }
      };
      reader.readAsDataURL(file);
    };
    input.click();
  };

  const updateRoleBadgeFromAvatar = () => {
    const avatar = localStorage.getItem("fisher_avatar");
    if (avatar && roleIcon) {
      roleIcon.innerHTML = `<img src="${avatar}" style="width:24px;height:24px;border-radius:50%;object-fit:cover" />`;
    }
  };

  // ── Canvas 分享海报 ──
  const generateSharePoster = (fish) => {
    const canvas = document.createElement("canvas");
    canvas.width = 600;
    canvas.height = 800;
    const ctx = canvas.getContext("2d");
    const tier = getGoalTier();
    const rarityGradients = {
      rare: ["#AB47BC", "#6A1B9A"],
      epic: ["#FF7043", "#BF360C"],
      legendary: ["#FFD700", "#FF6F00"],
    };
    const [c1, c2] = rarityGradients[fish.rarity] || ["#42A5F5", "#1565C0"];

    // Background gradient
    const grad = ctx.createLinearGradient(0, 0, 0, 800);
    grad.addColorStop(0, c1);
    grad.addColorStop(1, c2);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 600, 800);

    // Stars
    for (let i = 0; i < 30; i++) {
      ctx.fillStyle = `rgba(255,255,255,${0.3 + Math.random() * 0.5})`;
      ctx.beginPath();
      ctx.arc(Math.random() * 600, Math.random() * 400, 1 + Math.random() * 2, 0, Math.PI * 2);
      ctx.fill();
    }

    // Water wave
    ctx.fillStyle = "rgba(0,0,0,0.15)";
    ctx.beginPath();
    ctx.moveTo(0, 500);
    for (let x = 0; x <= 600; x += 10) {
      ctx.lineTo(x, 500 + Math.sin(x * 0.02) * 15 + Math.sin(x * 0.05 + 2) * 8);
    }
    ctx.lineTo(600, 800);
    ctx.lineTo(0, 800);
    ctx.fill();

    // Title
    ctx.fillStyle = "#fff"; ctx.font = "bold 36px sans-serif"; ctx.textAlign = "center";
    ctx.fillText("🎣 山海渔 · 战果分享", 300, 80);

    // Fish circle bg
    ctx.fillStyle = "rgba(255,255,255,0.15)";
    ctx.beginPath(); ctx.arc(300, 240, 80, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#fff"; ctx.font = "80px sans-serif";
    ctx.fillText("🐟", 300, 270);

    // Fish name + rarity
    ctx.font = "bold 28px sans-serif"; ctx.fillText(fish.name, 300, 360);
    ctx.font = "16px sans-serif"; ctx.fillStyle = "rgba(255,255,255,0.8)";
    ctx.fillText(`⭐ ${fish.rarity || "稀有"} · ${fish.coin}${fish.currency === "score" ? "积分" : "金币"}`, 300, 395);

    // Divider
    ctx.strokeStyle = "rgba(255,255,255,0.3)"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(100, 430); ctx.lineTo(500, 430); ctx.stroke();

    // Player info
    ctx.font = "18px sans-serif"; ctx.fillStyle = "rgba(255,255,255,0.9)";
    ctx.fillText(`${tier.icon} ${tier.name}`, 300, 480);
    ctx.font = "14px sans-serif";
    ctx.fillText(`🎣 鱼竿 Lv.${playerState ? playerState.rod_level : 0} · 📍 ${playerState ? playerState.spot_name : "—"}`, 300, 510);

    // CTA
    ctx.fillStyle = "rgba(255,255,255,0.9)"; ctx.fillRect(150, 640, 300, 50);
    ctx.fillStyle = c2; ctx.font = "bold 18px sans-serif";
    ctx.fillText("来山海渔 · 一竿一世界", 300, 672);
    ctx.fillStyle = "rgba(255,255,255,0.6)"; ctx.font = "12px sans-serif";
    ctx.fillText("扫码加入山海渔", 300, 720);

    // Show or download
    const img = canvas.toDataURL("image/png");
    const win = window.open("", "_blank", "width=600,height=800");
    if (win) {
      win.document.write(`<img src="${img}" style="width:100%" /><br><center><small>长按保存分享到朋友圈</small></center>`);
    } else {
      const a = document.createElement("a");
      a.href = img; a.download = `山海渔_${fish.name}.png`; a.click();
      showToast("海报已下载!", "success");
    }
  };

  // Area visual style (replaced by areaStyleById)

  // Fish species — loaded from API dynamically (replaces hardcoded fishData)
  let speciesBySpot = {};  // { spot_id: [{id,name,price,...}] }
  let allSpecies = [];

  // Fishing spots — loaded from API
  let apiSpots = [];

  // API player state snapshot
  let playerState = null;
  let apiInitialized = false;

  // State (local UI cache, truth from API)
  let coinNum = 200;
  let scoreNum = 0;
  let canPull = false;
  let curArea = "pond";
  let curSpotId = 0;  // API spot ID
  let curAge = "young";
  let fishBag = {};
  let items = { torch: false, float: false, raincoat: false, bait: false, hook: false };
  let isNight = false;
  let weather = "sunny";
  let surpriseTimer = null;
  let unlockedSpots = new Set([0]);  // API-managed spot unlock states
  let pendingFish = null;
  let lastHookPt = null;
  let hookNearEl = null;
  let fishPhase = "idle";
  let fightUntilTs = 0;
  let fightMeter01 = 0;
  let lastFightTapAt = 0;
  let tapRateEma = 0;
  let biteUntilTs = 0;
  let nextBubbleAt = 0;
  let bubbleBurstLeft = 0;
  let nextNearFishAt = 0;
  let nearShadowOnUntil = 0;
  let nextNearShadowAt = 0;
  let baitEl = null;
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

  const updateRodDisplay = (lv) => {
    const level = Number(lv || 0);
    setText(rodLv, `Lv.${level}`);
    setText(sysRodLv, `Lv.${level}`);
    if (rodBox) rodBox.setAttribute("data-rod", String(Math.min(15, level)));
    if (level >= 15) {
      setText(sysRodInfo, "已达最高等级！稀有率+150%，冷却-22.5%");
    } else {
      const nextCost = level + 1;
      setText(sysRodInfo, `下一级：稀有率+${(level+1)*10}%，冷却-${Math.round((level+1)*1.5)}%`);
    }
  };

  const doUpgradeRod = async () => {
    if (!window.FisherAPI || !apiInitialized) { showToast("API未连接", "error"); return; }
    try {
      const result = await window.FisherAPI._post("/v1/game/upgrade-rod", {});
      coinNum = result.coins;
      scoreNum = result.score;
      setText(coin, coinNum);
      setText(score, scoreNum);
      updateRodDisplay(result.rod_level);
      showToast(`鱼竿升级成功！Lv.${result.rod_level} 🎣`, "success");
    } catch (e) {
      showToast("升级失败：" + e.message, "error");
    }
  };

  const setFightHud = (on, meter01 = 0, text = "") => {
    if (!fightHud || !fightFill || !fightTxt) return;
    fightHud.classList.toggle("on", !!on);
    const pct = Math.max(0, Math.min(1, Number(meter01 || 0))) * 100;
    fightFill.style.width = `${pct.toFixed(1)}%`;
    if (text) fightTxt.textContent = String(text);
    // Hide direction hint when fight ends
    if (!on) {
      const fd = document.getElementById("fightDir");
      if (fd) fd.style.display = "none";
    }
  };

  const recyclePriceOf = (base) => Math.max(1, Math.floor(Math.max(1, Number(base || 1)) * 0.8));

  const saveState = () => {
    // UI-only prefs to localStorage (not game state - that's in API)
    try {
      const prefs = { curAge, items, isNight: isNight ? 1 : 0 };
      localStorage.setItem("fisher_ui_prefs_v2", JSON.stringify(prefs));
    } catch {}
  };
  const loadState = async () => {
    // Load UI prefs
    try {
      const raw = localStorage.getItem("fisher_ui_prefs_v2");
      if (raw) {
        const p = JSON.parse(raw);
        if (typeof p.curAge === "string") curAge = p.curAge;
        if (p.items && typeof p.items === "object") items = { ...items, ...p.items };
      }
    } catch {}
    // Init from API
    if (!window.FisherAPI) return;
    try {
      await window.FisherAPI.autoLogin();
      const [meData, spotsData, speciesData] = await Promise.all([
        window.FisherAPI.me(),
        window.FisherAPI.spots(),
        window.FisherAPI.species(null, true),
      ]);
      playerState = meData;
      allSpecies = speciesData;
      apiSpots = spotsData;
      coinNum = meData.coins;
      scoreNum = meData.score;
      curSpotId = meData.spot_id;
      updateRodDisplay(meData.rod_level || 0);
      // Restore equipment from API
      if (meData.equipment && Object.keys(meData.equipment).length > 0) {
        Object.keys(meData.equipment).forEach(k => { items[k] = true; });
        if (torch && items.torch) torch.style.display = isNight ? "block" : "none";
      }
      curArea = String(meData.spot_id);  // use spot_id as area key
      fishBag = {};
      if (meData.inventory) {
        Object.entries(meData.inventory).forEach(([sid, n]) => {
          const sp = speciesData.find(s => s.id === Number(sid));
          if (sp && n > 0) fishBag[sp.name] = { num: n, id: sp.id, coin: sp.price, currency: sp.currency };
        });
      }
      // Build speciesBySpot from API data
      speciesBySpot = {};
      speciesData.forEach(s => {
        if (!speciesBySpot[s.spot_id]) speciesBySpot[s.spot_id] = [];
        speciesBySpot[s.spot_id].push(s);
      });
      // Build unlocked spots from spots data (spot 0 always unlocked)
      unlockedSpots = new Set([0]);
      spotsData.forEach(s => {
        if (s.unlock_coins === 0 && s.unlock_score === 0 && s.unlock_rod_level === 0) unlockedSpots.add(s.id);
      });
      apiInitialized = true;
      console.log(`Fisher API ready: ${speciesData.length} species, ${spotsData.length} spots, ${coinNum} coins`);
    } catch (e) {
      console.warn("Fisher API init failed, using fallback:", e.message, "error");
    }
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

  const getAreas = () => {
    if (apiSpots.length > 0) {
      return apiSpots.map(s => ({
        id: String(s.id),
        name: s.name,
        unlockCoin: s.unlock_coins,
        unlockScore: s.unlock_score || 0,
        desc: s.description || "",
      })).sort((a, b) => Number(a.id) - Number(b.id));
    }
    // Fallback
    return [
      { id: "0", name: "乡村小河", unlockCoin: 0, desc: "新手练手" },
      { id: "1", name: "野外池塘", unlockCoin: 0, desc: "更多鱼种" },
    ];
  };

  const areaStyleById = (spotId) => {
    const id = Number(spotId || 0);
    const styles = {
      0: { // 乡村小河
        game: "game-pond", water: "water-pond",
        shadow: `<div class="fishShadow fs-pond-1"></div><div class="fishShadow fs-pond-2"></div>`,
        decor: `<div class="scene-decor plant pond-grass"></div><div class="scene-decor pond-flower"></div>
                <div class="scene-rocks" style="bottom:22%;right:8%"></div>
                <div class="waterRipple"></div><div class="waterRipple"></div>`,
      },
      1: { // 野外池塘
        game: "game-pond", water: "water-pond",
        shadow: `<div class="fishShadow fs-pond-1"></div><div class="fishShadow fs-pond-2"></div><div class="fishShadow fs-lake-1" style="top:80%;animation-duration:28s"></div>`,
        decor: `<div class="scene-trees"><div class="tree" style="--tree-color:#4a7a2e;left:10%;bottom:20%"></div><div class="tree" style="--tree-color:#5a8a3c;left:18%;bottom:24%;transform:scale(.7)"></div></div>
                <div class="scene-mountain"></div>
                <div class="waterRipple"></div><div class="waterRipple"></div>`,
      },
      2: { // 郊外湖泊
        game: "game-lake", water: "water-lake",
        shadow: `<div class="fishShadow fs-lake-1"></div><div class="fishShadow fs-lake-2"></div>`,
        decor: `<div class="scene-decor lake-lotus"></div>
                <div class="scene-mountain"></div>
                <div class="scene-boat" style="left:18%;bottom:14%"></div>
                <div class="waterRipple"></div><div class="waterRipple"></div><div class="waterRipple"></div>`,
      },
      3: { // 沿江堤坝
        game: "game-lake", water: "water-lake",
        shadow: `<div class="fishShadow fs-lake-2" style="width:45px;height:16px"></div><div class="fishShadow fs-sea-1"></div>`,
        decor: `<div class="scene-dock"></div>
                <div class="scene-mountain"></div>
                <div class="waterRipple"></div><div class="waterRipple"></div>`,
      },
      4: { // 近海码头
        game: "game-sea", water: "water-sea",
        shadow: `<div class="fishShadow fs-sea-1"></div><div class="fishShadow fs-sea-2"></div>`,
        decor: `<div class="scene-decor sea-coral"></div><div class="scene-decor sea-shell"></div>
                <div class="scene-boat" style="left:60%;bottom:15%;width:70px;height:18px"></div>
                <div class="waterRipple"></div><div class="waterRipple"></div><div class="waterRipple"></div>`,
      },
      5: { // 秘境暗流
        game: "game-deep", water: "water-deep",
        shadow: `<div class="fishShadow fs-deep-1"></div><div class="fishShadow fs-deep-2"></div>`,
        decor: `<div class="glowParticle"></div><div class="glowParticle"></div><div class="glowParticle"></div><div class="glowParticle"></div>
                <div class="waterRipple" style="border-color:rgba(100,200,255,.35)"></div><div class="waterRipple" style="border-color:rgba(100,200,255,.35)"></div>`,
      },
      6: { // 龙宫深渊
        game: "game-deep", water: "water-deep",
        shadow: `<div class="fishShadow fs-deep-2" style="top:52%"></div><div class="fishShadow fs-ancient-1" style="animation-duration:45s"></div>`,
        decor: `<div class="glowParticle"></div><div class="glowParticle"></div><div class="glowParticle"></div><div class="glowParticle"></div>
                <div class="scene-decor sea-coral" style="opacity:.4;transform:scale(2)"></div>
                <div class="waterRipple" style="border-color:rgba(150,120,255,.35)"></div><div class="waterRipple" style="border-color:rgba(150,120,255,.35)"></div>`,
      },
      7: { // 远古海域
        game: "game-ancient", water: "water-ancient",
        shadow: `<div class="fishShadow fs-ancient-1"></div><div class="fishShadow fs-ancient-2"></div>`,
        decor: `<div class="glowParticle" style="background:rgba(255,100,180,.8)"></div><div class="glowParticle" style="background:rgba(200,80,255,.7)"></div><div class="glowParticle" style="background:rgba(255,100,180,.6)"></div><div class="glowParticle" style="background:rgba(200,80,255,.7)"></div>
                <div class="waterRipple" style="border-color:rgba(255,120,180,.4)"></div><div class="waterRipple" style="border-color:rgba(200,100,255,.35)"></div>`,
      },
    };
    return styles[id] || styles[0];
  };

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
    // Click avatar to upload custom
    roleBadge && roleBadge.addEventListener("click", avatarUpload);
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
    const depth = curSpotId >= 5 ? 156 : (curSpotId >= 3 ? 140 : 124);
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
    const pool = speciesBySpot[curSpotId] || allSpecies || [];
    if (pool.length === 0) return { id: 1, name: "白条", coin: 8, currency: "coin", _rare: false };
    // Weather bonus
    let weatherBonus = 1.0;
    if (weather === "rain") weatherBonus = 1.15;      // 雨天+15%
    if (weather === "storm") weatherBonus = 1.35;      // 风暴+35%
    if (weather === "snow") weatherBonus = 1.08;       // 雪天微升
    if (weather === "fog") weatherBonus = 1.06;
    // Rarity weights with weather
    const baseWeights = { common: 50, uncommon: 25, rare: 12, epic: 5, legendary: 1 };
    const items_w = pool.map(s => {
      const bw = baseWeights[s.rarity] || 10;
      return s.rarity !== "common" ? bw * weatherBonus : bw;
    });
    // Weighted random or simple random
    const chosen = Math.random() < 0.7
      ? (() => { const total = items_w.reduce((a,b) => a+b, 0); let r = Math.random() * total; for (let i = 0; i < pool.length; i++) { r -= items_w[i]; if (r <= 0) return pool[i]; } return pool[pool.length-1]; })()
      : pool[Math.floor(Math.random() * pool.length)];
    const isRare = chosen.rarity === "rare" || chosen.rarity === "epic" || chosen.rarity === "legendary";
    return { ...chosen, coin: chosen.price, _rare: isRare, _rarity: chosen.rarity };
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

  // Area / Spot switching (API-backed)
  const setArea = (a) => {
    const id = String(a || "0");
    const spotId = Number(id);
    if (!unlockedSpots.has(spotId)) {
      if (areaMask) areaMask.style.display = "flex";
      renderAreaMenu();
      return;
    }
    curArea = id;
    curSpotId = spotId;
    const style = areaStyleById(spotId);
    gameBox.classList.remove("game-pond", "game-lake", "game-sea", "game-deep", "game-ancient");
    gameBox.classList.add(style.game);
    waterBox.classList.remove("water-pond", "water-lake", "water-sea", "water-deep", "water-ancient");
    waterBox.classList.add(style.water);
    fishShadows.innerHTML = style.shadow;
    sceneDecor.innerHTML = style.decor;
    // Sync to API
    if (apiInitialized && window.FisherAPI) {
      window.FisherAPI.switchSpot(spotId).catch(() => {});
    }
    saveState();
  };

  const renderAreaMenu = () => {
    if (!areaList) return;
    areaList.innerHTML = "";
    const areas = getAreas();
    areas.forEach((a) => {
      const unlocked = unlockedSpots.has(Number(a.id));
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
      row.addEventListener("click", async () => {
        if (unlocked) {
          setArea(a.id);
          if (areaMask) areaMask.style.display = "none";
          return;
        }
        const need = Math.max(0, Number(a.unlockCoin || 0));
        if (coinNum < need) showToast("金币不足", "error"); return;
        if (areaList.dataset.pending !== a.id) {
          areaList.dataset.pending = a.id;
          showSurprise(`再次点击确认解锁：${a.name}（${need}金币）`);
          renderAreaMenu();
          return;
        }
        // Confirm unlock via API
        areaList.dataset.pending = "";
        if (apiInitialized && window.FisherAPI) {
          try {
            await window.FisherAPI.switchSpot(Number(a.id));
            unlockedSpots.add(Number(a.id));
          } catch (e) {
            showToast("解锁失败: " + e.message, "error");
            renderAreaMenu();
            return;
          }
        } else {
          coinNum -= need;
          unlockedSpots.add(Number(a.id));
        }
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

  // ── 仓库弹窗面板 ──

  // ── 背包面板（鱼获 + 道具两标签页） ──
  let bagTab = "fish";

  const renderFishTab = () => {
    const bagContent = document.getElementById("bagContent");
    if (!bagContent) return;
    const names = Object.keys(fishBag).filter(k => fishBag[k] && fishBag[k].num > 0);
    let total = 0;
    names.forEach(nm => { total += fishBag[nm].num; });
    document.getElementById("bagCoin") && (document.getElementById("bagCoin").textContent = String(coinNum));
    document.getElementById("bagScore") && (document.getElementById("bagScore").textContent = String(scoreNum));
    document.getElementById("bagKinds") && (document.getElementById("bagKinds").textContent = String(names.length));
    document.getElementById("bagTotal") && (document.getElementById("bagTotal").textContent = String(total));

    let html = `<div class="bagSummary">
      <div class="row" style="gap:8px;flex-wrap:wrap;margin-bottom:8px">
        <div class="pill">💰<b id="bagCoin">${coinNum}</b></div>
        <div class="pill">⭐<b id="bagScore">${scoreNum}</b></div>
        <div class="pill">🐟<b id="bagKinds">${names.length}</b>种</div>
        <div class="pill">📦<b id="bagTotal">${total}</b>条</div>
      </div>
      <button class="miniBtn primary" id="btnSellAllInline">一键出售（全部）</button>
    </div>`;

    if (!names.length) {
      html += `<div class="emptyHint">暂无鱼获，去抛竿钓几条吧</div>`;
      bagContent.innerHTML = html;
      return;
    }

    html += `<div id="bagList">`;
    names.sort((a, b) => a.localeCompare(b, "zh-CN")).forEach(nm => {
      const f = fishBag[nm];
      const base = Number(f.coin || 1);
      const sellPrice = recyclePriceOf(base);
      html += `<div class="bagRow">
        <div class="bagL">
          <img alt="${nm}" src="${fishIconSrc(f.id)}" />
          <div style="min-width:0">
            <div class="bagNm">${nm}</div>
            <div class="bagMeta">${f.num}条 · 出售${sellPrice}/条</div>
          </div>
        </div>
        <div class="bagR">
          <button class="miniBtn" data-sell1="${encodeURIComponent(nm)}">出售1条</button>
          <button class="miniBtn danger" data-sellall="${encodeURIComponent(nm)}">全部</button>
        </div>
      </div>`;
    });
    html += `</div>`;
    bagContent.innerHTML = html;

    // Sell events
    const btnSellAllInline = document.getElementById("btnSellAllInline");
    btnSellAllInline && btnSellAllInline.addEventListener("click", async () => {
      if (await customConfirm("确定将仓库里的鱼获全部出售为金币？")) sellAllBagFish();
    });
    const bagList = document.getElementById("bagList");
    bagList && bagList.addEventListener("click", (e) => {
      const t = e.target;
      if (!t) return;
      const sell1 = t.closest && t.closest("[data-sell1]");
      if (sell1) { sellBagFish(decodeURIComponent(sell1.getAttribute("data-sell1")), false); return; }
      const sellall = t.closest && t.closest("[data-sellall]");
      if (sellall) { sellBagFish(decodeURIComponent(sellall.getAttribute("data-sellall")), true); return; }
    });
  };

  const renderItemsTab = () => {
    const bagContent = document.getElementById("bagContent");
    if (!bagContent) return;
    const curLv = playerState ? playerState.rod_level : 0;

    // Equipment row
    const equipKeys = Object.keys(items).filter(k => items[k]);
    const equipNames = { torch: "🔦 手电筒（夜间照亮）", bait: "🥚 鱼饵（吸引大鱼）", hook: "🪝 锋利钩（稳中鱼）", raincoat: "☔ 雨衣（雨天从容）", float_pro: "🎣 高级鱼漂（咬钩更明显）" };

    let html = `<div style="font-weight:500;margin-bottom:8px">🎒 背包道具</div>`;
    if (equipKeys.length === 0) {
      html += `<div class="emptyHint">还没有道具，快去道具商店购买吧</div>`;
    } else {
      equipKeys.forEach(k => {
        html += `<div style="padding:6px 8px;background:#f8fafc;border-radius:8px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">
          <span>${equipNames[k] || k}</span><span style="font-size:12px;color:#4CAF50">✓ 已拥有</span>
        </div>`;
      });
    }
    html += `<button class="miniBtn primary" id="btnShopFromBag" style="margin:8px 0">🛒 道具商店</button>`;

    // Rod switching
    html += `<div style="font-weight:500;margin:14px 0 8px">🎣 鱼竿切换（当前: ${ROD_STYLES[curLv]?.name || 'Lv.'+curLv}）</div>`;
    html += `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:5px">`;
    ROD_STYLES.forEach(r => {
      const owned = r.lv <= curLv;
      const active = r.lv === curLv;
      html += `<div class="rod-slot ${active?'active':''} ${!owned?'locked':''}"
        data-rod="${r.lv}" title="${r.name} · ${r.desc}"
        style="background:${owned?r.color+'18':'#f5f5f5'};border:2px solid ${active?r.color:owned?'#e0e0e0':'#f0f0f0'};border-radius:10px;padding:5px;text-align:center;${!owned?'opacity:.4':''};cursor:${owned?'pointer':'default'}">
        <div style="font-size:${active?'26':'20'}px">${r.emoji}</div>
        <div style="font-size:9px;font-weight:600;color:${owned?r.color:'#bbb'}">${r.name}</div>
        <div style="font-size:8px;color:${active?r.color:'#aaa'}">${active?'⚡使用中':owned?'Lv.'+r.lv:'🔒'}</div>
      </div>`;
    });
    html += `</div>`;
    html += `<div style="font-size:11px;color:#888;margin-top:6px;text-align:center">点击已解锁的鱼竿即可切换使用（可自由切换）</div>`;

    bagContent.innerHTML = html;

    // Shop from bag
    const btnShopFromBag = document.getElementById("btnShopFromBag");
    btnShopFromBag && btnShopFromBag.addEventListener("click", () => {
      document.querySelectorAll(".shopItem[data-buy]").forEach(el => {
        const key = el.dataset.buy;
        el.classList.toggle("owned", !!items[key]);
      });
      openMask(shopMask);
    });

    // Rod switching events
    bagContent.querySelectorAll(".rod-slot").forEach(slot => {
      slot.addEventListener("click", async () => {
        const lv = Number(slot.dataset.rod);
        const curLvNow = playerState ? playerState.rod_level : 0;
        if (lv > curLvNow) { showToast("该鱼竿尚未解锁，请先升级", "error"); return; }
        if (lv === curLvNow) { showToast("已经是当前鱼竿啦", ""); return; }
        // Switch rod via API
        try {
          if (window.FisherAPI && apiInitialized) {
            await window.FisherAPI._post("/v1/game/switch-rod", { rod_level: lv });
          }
          playerState = playerState || {};
          playerState.rod_level = lv;
          updateRodDisplay(lv);
          showToast(`已切换为 ${ROD_STYLES[lv]?.name || 'Lv.'+lv}`, "success");
          renderItemsTab();
        } catch(e) { showToast(e.message, "error"); }
      });
    });
  };

  const renderBagPanel = () => {
    if (bagTab === "items") { renderItemsTab(); return; }
    renderFishTab();
  };

  const sellBagFish = async (nm, all = false) => {
    const f = fishBag[nm];
    if (!f || f.num <= 0) return;
    if (!all && window.FisherAPI && apiInitialized) {
      try {
        await window.FisherAPI.sell(false, f.id, 1);
        const meData = await window.FisherAPI.me();
        coinNum = meData.coins; scoreNum = meData.score;
        fishBag = {};
        if (meData.inventory) {
          const sp = allSpecies || [];
          Object.entries(meData.inventory).forEach(([sid, n]) => {
            const s = sp.find(x => x.id === Number(sid));
            if (s && n > 0) fishBag[s.name] = { num: n, id: s.id, coin: s.price };
          });
        }
      } catch { /* fall through to local */ }
    }
    const qty = all ? f.num : 1;
    const gain = recyclePriceOf(f.coin) * qty;
    coinNum += gain;
    f.num -= qty;
    if (f.num <= 0) delete fishBag[nm];
    setText(coin, coinNum);
    refreshStorage();
    renderBagPanel();
    saveState();
  };

  const sellAllBagFish = async () => {
    if (window.FisherAPI && apiInitialized) {
      try {
        await window.FisherAPI.sell(true);
        const meData = await window.FisherAPI.me();
        coinNum = meData.coins; scoreNum = meData.score;
        fishBag = {};
        if (meData.inventory) {
          const sp = allSpecies || [];
          Object.entries(meData.inventory).forEach(([sid, n]) => {
            const s = sp.find(x => x.id === Number(sid));
            if (s && n > 0) fishBag[s.name] = { num: n, id: s.id, coin: s.price };
          });
        }
      } catch {}
    }
    if (!window.FisherAPI || !apiInitialized) {
      let gain = 0;
      Object.keys(fishBag).forEach(nm => {
        const f = fishBag[nm];
        if (!f || f.num <= 0) return;
        gain += recyclePriceOf(f.coin) * f.num;
      });
      coinNum += gain;
      fishBag = {};
    }
    setText(coin, coinNum);
    refreshStorage();
    renderBagPanel();
    saveState();
  };

  const buyItem = async (name, price) => {
    const p = Math.max(0, Number(price || 0));
    // Try API first
    if (window.FisherAPI && apiInitialized) {
      try {
        const result = await window.FisherAPI._post("/v1/game/buy-item", { item_key: name });
        coinNum = result.coins;
        setText(coin, coinNum);
        // Update local equipment state
        if (result.equipment) {
          items[name] = true;
          if (name === "torch" && torch) torch.style.display = isNight ? "block" : "none";
        }
        showToast(`${result.equipment.name}（耐久${result.equipment.durability}）`);
        saveState();
        return;
      } catch (e) {
        showToast("购买失败：" + e.message, "error");
        return;
      }
    }
    // Fallback local
    if (coinNum < p) showToast("金币不足", "error"); return;
    if (name === "hook" && items.hook) showToast("已有锋利钩", "error"); return;
    coinNum -= p;
    stats.spentCoin = Number(stats.spentCoin || 0) + p;
    items[name] = true;
    setText(coin, coinNum);
    showToast("购买成功!", "success");
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

      // Vibration feedback（按鱼的大小分级震动）
      const vibOn = getOpt(LS.vibrate, "on") !== "off";
      if (vibOn && navigator.vibrate) {
        const intensity = fish._rare ? 120 : 60;
        navigator.vibrate([intensity, 80, intensity]);
      }

      // Direction hint（提示鱼挣扎方向）
      const fightDir = document.getElementById("fightDir");
      if (fightDir) {
        fightDir.style.display = "block";
        const dirs = ["⬅️ 向左拉", "➡️ 向右拉", "⬆️ 松一点", "⬇️ 紧一点"];
        fightDir.textContent = dirs[Math.floor(Math.random() * 4)];
        fightDir.style.opacity = "1";
        setTimeout(() => { if (fightDir) fightDir.style.opacity = "0.5"; }, 600);
      }

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

    if (!fishBag[fish.name]) fishBag[fish.name] = { num: 0, id: fish.id, coin: fish.coin, currency: fish.currency };
    fishBag[fish.name].num += 1;

    // Quest tracking
    updateQuest("fishCaught", 1);
    updateQuest("coinsEarned", add);
    if (fish._rare) updateQuest("rareCaught", 1);

    // Async sync to API (fire-and-forget, best effort)
    if (apiInitialized && window.FisherAPI) {
      window.FisherAPI.fish().then(data => {
        coinNum = data.inventory ? coinNum : coinNum;  // server state is truth
      }).catch(() => {});  // silent fail, local state is primary for UX
    }

    if (fishTip) {
      fishTip.textContent = `钓获：${fish.name} +${add}金币`;
      fishTip.classList.add("show");
    }

    // Track rare catch for share
    if (fish._rare && fish._rarity && fish._rarity !== "common" && fish._rarity !== "uncommon") {
      lastRareCatch = { name: fish.name, coin: fish.coin, currency: fish.currency || "coin", rarity: fish._rarity };
      if (btnShare) { btnShare.style.display = ""; btnShare.textContent = `📤晒 "${fish.name}"`; }
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
  // ── 弹层叠加管理（避免后开的弹层被前面的盖住） ──
  let _maskZBase = 999;
  const _maskStack = []; // stack of [element, savedZ]

  const openMask = (m) => {
    if (!m) return;
    // 避免重复入栈（若已在栈里则直接提升 z 到顶层）
    const existIdx = _maskStack.findIndex(([el]) => el === m);
    if (existIdx !== -1) _maskStack.splice(existIdx, 1);
    _maskStack.push([m, m.style.zIndex || ""]);
    // 按栈顺序重新分配 z-index，后入栈的始终更高
    _maskStack.forEach(([el], i) => { el.style.zIndex = _maskZBase + i + 1; });
    m.style.display = "flex";
  };
  const closeMask = (m) => {
    if (!m) return;
    m.style.display = "none";
    m.style.zIndex = "";
    const idx = _maskStack.findIndex(([el]) => el === m);
    if (idx !== -1) _maskStack.splice(idx, 1);
    // 关闭后重新整理剩余弹层的 z-index
    _maskStack.forEach(([el], i) => { el.style.zIndex = _maskZBase + i + 1; });
  };

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
    btnShop && btnShop.addEventListener("click", () => {
      document.querySelectorAll(".shopItem[data-buy]").forEach(el => {
        const key = el.dataset.buy;
        el.classList.toggle("owned", !!items[key]);
      });
      openMask(shopMask);
    });
    btnBag && btnBag.addEventListener("click", () => { openMask(bagMask); renderBagPanel(); });
    const btnBagClose = document.getElementById("btnBagClose");
    btnBagClose && btnBagClose.addEventListener("click", () => closeMask(bagMask));

    // Bag tab switching
    const tabFish = document.getElementById("tabFish");
    const tabItems = document.getElementById("tabItems");
    tabFish && (tabFish.onclick = () => {
      bagTab = "fish";
      tabFish.classList.add("primary");
      tabItems && tabItems.classList.remove("primary");
      renderBagPanel();
    });
    tabItems && (tabItems.onclick = () => {
      bagTab = "items";
      tabItems.classList.add("primary");
      tabFish && tabFish.classList.remove("primary");
      renderBagPanel();
    });

    // Empire / Fishery Management
    const btnEmpire = document.getElementById("btnEmpire");
    const empireMask = document.getElementById("empireMask");
    const empireContent = document.getElementById("empireContent");
    const btnEmpireClose = document.getElementById("btnEmpireClose");
    btnEmpire && btnEmpire.addEventListener("click", () => { openMask(empireMask); renderEmpirePanel(); });
    btnEmpireClose && btnEmpireClose.addEventListener("click", () => closeMask(empireMask));

    // Market (hidden in compliance mode - P2P trading not allowed)
    const btnMarket = document.getElementById("btnMarket");
    const marketMask = document.getElementById("marketMask");
    const marketContent = document.getElementById("marketContent");
    const btnMarketClose = document.getElementById("btnMarketClose");
    if (btnMarket) {
      if (window.FisherConfig && window.FisherConfig.COMPLIANCE_MODE) {
        btnMarket.style.display = "none";
      } else {
        btnMarket.addEventListener("click", () => { openMask(marketMask); renderMarketPanel(); });
      }
    }
    btnMarketClose && btnMarketClose.addEventListener("click", () => closeMask(marketMask));

    // ══════════════════════════════════════════
    // 社区面板
    // ══════════════════════════════════════════
    let communityTab = "club";
    const communityContent = document.getElementById("communityContent");
    const communityMask = document.getElementById("communityMask");
    const btnCommunityClose = document.getElementById("btnCommunityClose");
    const tabClub = document.getElementById("tabClub");
    const tabCatch = document.getElementById("tabCatch");
    const tabRank = document.getElementById("tabRank");
    const tabShow = document.getElementById("tabShow");

    const switchCommunityTab = (tab) => {
      communityTab = tab;
      [tabClub, tabCatch, tabRank, tabShow].forEach((b, i) => {
        const names = ["club", "catch", "rank", "show"];
        b && b.classList.toggle("primary", names[i] === tab);
      });
      renderCommunityPanel();
    };
    tabClub && (tabClub.onclick = () => switchCommunityTab("club"));
    tabCatch && (tabCatch.onclick = () => switchCommunityTab("catch"));
    tabRank && (tabRank.onclick = () => switchCommunityTab("rank"));
    tabShow && (tabShow.onclick = () => switchCommunityTab("show"));

    btnCommunity && btnCommunity.addEventListener("click", () => {
      communityTab = "club"; // 每次打开强制重置到俱乐部
      [tabClub, tabCatch, tabRank, tabShow].forEach((b, i) => {
        b && b.classList.toggle("primary", i === 0);
      });
      openMask(communityMask);
      renderCommunityPanel();
    });
    btnCommunityClose && (btnCommunityClose.onclick = () => closeMask(communityMask));

    const renderCommunityPanel = () => {
      if (!communityContent) return;
      if (communityTab === "club") renderClubTab();
      else if (communityTab === "catch") renderCatchTab();
      else if (communityTab === "rank") renderRankTab();
      else renderShowTab();
    };

    // 俱乐部 Tab
    const renderClubTab = () => {
      const cur = getGoalTier();
      let html = `<div style="text-align:center;padding:12px 0">
        <div style="font-size:56px">${cur.icon}</div>
        <div style="font-size:18px;font-weight:600;color:#333;margin-top:6px">${cur.name}</div>
        <div style="font-size:13px;color:#888;margin-top:4px">🏆 阅历 ${scoreNum} · 💰 ${coinNum}金币</div>
      </div>`;
      html += `<div style="font-weight:500;margin-bottom:8px">📢 俱乐部公告</div>`;
      html += `<div style="background:#f0f7ff;border-radius:12px;padding:14px;margin-bottom:12px">
        <div style="font-weight:600;margin-bottom:6px">🌊 欢迎来到山海渔俱乐部</div>
        <div style="font-size:13px;color:#555;line-height:1.6">这里汇聚了天下钓友。分享你的渔获，结识同好，共同成长。每日签到、完成任务即可获得丰厚奖励！</div>
      </div>`;
      html += `<div style="font-weight:500;margin-bottom:8px">🎯 近期活动</div>`;
      const events = [
        { icon: "🎣", title: "周末钓鱼赛", desc: "周六/日 20:00-22:00 钓获双倍金币", tag: "进行中", tagColor: "#4CAF50" },
        { icon: "🏆", title: "月度排行榜", desc: "本月排名前10可获传说鱼竿皮肤", tag: "进行中", tagColor: "#4CAF50" },
        { icon: "🎁", title: "新用户礼包", desc: "注册即送鱼饵×5 + 新手鱼竿外观", tag: "永久", tagColor: "#FF9800" },
      ];
      events.forEach(e => {
        html += `<div style="padding:10px;border-bottom:1px solid #eee;display:flex;align-items:center;gap:10px">
          <div style="font-size:26px">${e.icon}</div>
          <div style="flex:1">
            <div style="font-weight:600;font-size:13px">${e.title}</div>
            <div style="font-size:11px;color:#888">${e.desc}</div>
          </div>
          <span style="font-size:11px;padding:2px 8px;border-radius:10px;background:${e.tagColor}20;color:${e.tagColor}">${e.tag}</span>
        </div>`;
      });
      html += `<button class="btnOk primary" style="width:100%;margin-top:14px;background:#55a3c9" onclick="showToast('敬请期待更多俱乐部功能！','success')">🏠 进入俱乐部大厅</button>`;
      communityContent.innerHTML = html;
    };

    // 真实渔获 Tab（支持文字/图片/短视频嵌入）
    const renderCatchTab = () => {
      const catches = [
        { type: "card", icon: "🐟", name: "小鲤鱼", loc: "郊外湖泊", user: "钓友李哥", time: "2小时前", rare: "", video: null },
        { type: "card", icon: "🐠", name: "小丑鱼", loc: "近海码头", user: "渔隐小红", time: "3小时前", rare: "", video: null },
        { type: "card", icon: "🐉", name: "传说龙鱼", loc: "龙宫深渊", user: "海王老张", time: "5小时前", rare: "🔥传说", video: null },
        { type: "video", platform: "douyin", videoId: "7356220878948831522", title: "龙鱼出水全过程！", user: "海王老张", time: "今天", rare: "🔥传说" },
        { type: "card", icon: "🐟", name: "巨型鲤鱼", loc: "沿江堤坝", user: "山海客", time: "昨天", rare: "", video: null },
        { type: "video", platform: "xiaohongshu", noteId: "65e3f2d0000000001e02d8f7", title: "周末爆箱实录🎣", user: "深海猎人", time: "昨天", rare: "⭐史诗" },
        { type: "card", icon: "🐬", name: "海豚", loc: "秘境暗流", user: "深海猎人", time: "昨天", rare: "⭐史诗", video: null },
      ];

      // 视频卡片（抖音/小红书均不支持 iframe，改用外链预览卡，点击播放跳转 App/网页）
      const embedVideo = (c) => {
        if (c.platform === "douyin") {
          const url = `https://www.douyin.com/video/${c.videoId}`;
          return `<div style="margin-top:8px;border-radius:12px;overflow:hidden;border:1.5px solid #250d00;background:#1a1a1a">
            <div style="padding:12px 14px;display:flex;align-items:center;gap:10px">
              <div style="font-size:28px">🎵</div>
              <div style="flex:1">
                <div style="font-weight:700;color:#fff;font-size:13px">${c.title}</div>
                <div style="font-size:11px;color:#888;margin-top:2px">@${c.user} · ${c.time}</div>
              </div>
              <a href="${url}" target="_blank" rel="noopener" onclick="event.stopPropagation()"
                 style="background:linear-gradient(135deg,#25f4ee,#fe2c55);color:#fff;border-radius:8px;padding:8px 14px;font-size:13px;font-weight:700;text-decoration:none;flex-shrink:0;display:flex;align-items:center;gap:4px">
                ▶ 播放
              </a>
            </div>
            <div style="background:linear-gradient(135deg,#25f4ee22,#fe2c5522);padding:6px 14px;font-size:11px;color:rgba(255,255,255,.45)">
              🎵 抖音 · 点击「播放」在抖音 App/网页观看完整视频
            </div>
          </div>`;
        } else if (c.platform === "xiaohongshu") {
          const url = `https://www.xiaohongshu.com/explore/${c.noteId}`;
          return `<div style="margin-top:8px;border-radius:12px;overflow:hidden;border:1.5px solid #ff4d4f">
            <div style="background:linear-gradient(135deg,#ff4d4f,#ff6b6b);padding:12px 14px;display:flex;align-items:center;gap:10px">
              <div style="font-size:28px">📕</div>
              <div style="flex:1">
                <div style="font-weight:700;color:#fff;font-size:13px">${c.title}</div>
                <div style="font-size:11px;color:rgba(255,255,255,.75);margin-top:2px">@${c.user} · ${c.time}</div>
              </div>
              <a href="${url}" target="_blank" rel="noopener" onclick="event.stopPropagation()"
                 style="background:#fff;color:#ff4d4f;border-radius:8px;padding:8px 14px;font-size:13px;font-weight:700;text-decoration:none;flex-shrink:0;display:flex;align-items:center;gap:4px">
                ▶ 播放
              </a>
            </div>
            <div style="padding:6px 14px;font-size:11px;color:#999">
              📕 小红书 · 点击「播放」在小红书 App/网页观看完整笔记
            </div>
          </div>`;
        }
        return "";
      };

      let html = `<div style="font-size:12px;color:#888;margin-bottom:10px;text-align:center">🌊 来自钓友们的真实渔获分享</div>`;
      catches.forEach(c => {
        if (c.type === "video") {
          html += `<div style="border-bottom:1px solid #eee;padding:12px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
              <div style="font-size:22px">🎬</div>
              <div style="flex:1">
                <div style="font-weight:600;font-size:13px">${c.title} <span style="font-size:11px;color:${c.rare==='🔥传说'?'#e74c3c':'#9b59b6'}">${c.rare}</span></div>
                <div style="font-size:11px;color:#888">${c.user} · ${c.time}</div>
              </div>
              <div style="font-size:18px">❤️</div>
            </div>${embedVideo(c)}</div>`;
        } else {
          html += `<div style="padding:12px;border-bottom:1px solid #eee;display:flex;align-items:center;gap:10px">
            <div style="font-size:36px;width:50px;text-align:center">${c.icon}</div>
            <div style="flex:1">
              <div style="font-weight:600;font-size:14px">${c.name} <span style="font-size:11px;color:${c.rare==='🔥传说'?'#e74c3c':c.rare==='⭐史诗'?'#9b59b6':'#888'}">${c.rare}</span></div>
              <div style="font-size:11px;color:#888">📍${c.loc} · ${c.user} · ${c.time}</div>
            </div>
            <div style="font-size:22px">❤️</div>
          </div>`;
        }
      });

      // 分享表单：支持图文+视频链接
      html += `
        <div style="margin-top:16px;padding:14px;background:#f9f9f9;border-radius:12px">
          <div style="font-weight:600;margin-bottom:10px;font-size:13px">📸 分享我的渔获</div>
          <input id="catchUser" type="text" placeholder="你的昵称" style="width:100%;padding:8px 10px;border:1px solid #ddd;border-radius:8px;margin-bottom:8px;font-size:13px;box-sizing:border-box">
          <input id="catchLoc" type="text" placeholder="钓获地点（如：郊外湖泊）" style="width:100%;padding:8px 10px;border:1px solid #ddd;border-radius:8px;margin-bottom:8px;font-size:13px;box-sizing:border-box">
          <input id="catchUrl" type="url" placeholder="视频链接（可选）：抖音/小红书链接" style="width:100%;padding:8px 10px;border:1px solid #ddd;border-radius:8px;margin-bottom:8px;font-size:13px;box-sizing:border-box">
          <div style="font-size:11px;color:#aaa;margin-bottom:8px">支持抖音、小红书视频链接发布，点「播放」跳转 App 观看</div>
          <button class="btnOk" style="width:100%;background:#4CAF50;font-size:13px" id="btnShareCatch">🚀 发布渔获</button>
        </div>`;
      communityContent.innerHTML = html;

      // 分享按钮事件
      const btnShareCatch = document.getElementById("btnShareCatch");
      btnShareCatch && (btnShareCatch.onclick = () => {
        const user = document.getElementById("catchUser")?.value.trim();
        const loc = document.getElementById("catchLoc")?.value.trim();
        const url = document.getElementById("catchUrl")?.value.trim();
        if (!user) { showToast("请输入昵称", "error"); return; }
        if (!loc) { showToast("请输入钓获地点", "error"); return; }
        if (url && !/douyin\.com|iesdouyin\.com|xiaohongshu\.com/i.test(url)) {
          showToast("仅支持抖音或小红书链接", "error"); return;
        }
        showToast("渔获已发布！🎣", "success");
        // 清空表单
        document.getElementById("catchUser").value = "";
        document.getElementById("catchLoc").value = "";
        document.getElementById("catchUrl").value = "";
      });
    };

    // 排行榜 Tab
    const renderRankTab = () => {
      const ranks = [
        { rank: 1, icon: "🥇", name: "海王老张", score: 9840, rod: "龙纹竿" },
        { rank: 2, icon: "🥈", name: "深海猎人", score: 8620, rod: "黄金竿" },
        { rank: 3, icon: "🥉", name: "钓友李哥", score: 7100, rod: "暗金竿" },
        { rank: 4, icon: "4", name: "山海客", score: 5530, rod: "紫晶竿" },
        { rank: 5, icon: "5", name: "渔隐小红", score: 4200, rod: "玄冰竿" },
        { rank: 6, icon: "6", name: "（你）", score: scoreNum, rod: `Lv.${playerState ? playerState.rod_level : 0}` },
      ];
      const playerRank = 6;
      let html = `<div style="font-weight:500;margin-bottom:8px">🏆 月度阅历排行榜</div>`;
      html += `<div style="font-size:12px;color:#888;margin-bottom:10px">每月1日重置，上榜赢传说鱼竿皮肤</div>`;
      ranks.forEach(r => {
        const isYou = r.name.includes("（你）");
        html += `<div style="padding:10px 8px;border-bottom:1px solid #eee;display:flex;align-items:center;gap:8px;background:${isYou?'#fff8e1':''};border-radius:${isYou?'8px':''}">
          <div style="font-size:18px;width:24px;text-align:center;font-weight:600;color:${r.rank<=3?'#d4a020':'#888'}">${r.icon}</div>
          <div style="flex:1"><div style="font-weight:${isYou?'700':'500'};font-size:13px">${r.name}</div><div style="font-size:11px;color:#aaa">${r.rod}</div></div>
          <div style="font-size:14px;font-weight:600;color:#FF9800">⭐${r.score.toLocaleString()}</div>
        </div>`;
      });
      html += `<div style="font-size:12px;color:#aaa;text-align:center;margin-top:10px">📅 月榜 · 数据每小时更新</div>`;
      communityContent.innerHTML = html;
    };

    // 展示台 Tab
    const renderShowTab = () => {
      const showcase = [
        { icon: "🐉", name: "龙纹竿", desc: "龙纹镌刻，传承之器", rarity: "传说", color: "#d4a020" },
        { icon: "🦅", name: "凤翎竿", desc: "凤凰翎羽，轻盈如风", rarity: "传说", color: "#d4af37" },
        { icon: "👑", name: "海神竿", desc: "海神亲赐，统御七海", rarity: "传说", color: "#ff3b3b" },
        { icon: "🐬", name: "海豚姐姐", desc: "传说渔获，超稀有", rarity: "史诗", color: "#9b59b6" },
        { icon: "🐟", name: "锦鲤王", desc: "旺财添福，钓到好运", rarity: "稀有", color: "#e67e22" },
      ];
      let html = `<div style="font-size:12px;color:#888;margin-bottom:10px;text-align:center">🎨 钓友装备与渔获展示台</div>`;
      showcase.forEach(s => {
        html += `<div style="background:${s.color}15;border:2px solid ${s.color}40;border-radius:14px;padding:14px;margin-bottom:10px;display:flex;align-items:center;gap:12px">
          <div style="font-size:40px">${s.icon}</div>
          <div style="flex:1">
            <div style="font-weight:700;font-size:15px;color:${s.color}">${s.name}</div>
            <div style="font-size:12px;color:#666">${s.desc}</div>
            <div style="font-size:11px;padding:2px 8px;display:inline-block;border-radius:8px;background:${s.color}25;color:${s.color};margin-top:4px">${s.rarity}</div>
          </div>
          <div style="font-size:18px">👁️</div>
        </div>`;
      });
      html += `<button class="btnOk" style="width:100%;margin-top:6px;background:#7f77dd" onclick="showToast('展示台功能即将开放！','success')">🎨 上传我的展品</button>`;
      communityContent.innerHTML = html;
    };

    // ══════════════════════════════════════════
    // 漂流瓶
    // ══════════════════════════════════════════
    const bottleFloat = document.getElementById("bottleFloat");
    const bottleMask = document.getElementById("bottleMask");
    const bottleContent = document.getElementById("bottleContent");
    const btnBottleClose = document.getElementById("btnBottleClose");

    let bottleActive = false;
    let bottleCooldown = false;

    // 漂流瓶动画（从右向左漂过水面）
    const spawnBottle = () => {
      if (!bottleFloat || bottleActive || !canPull) return;
      bottleActive = true;
      bottleFloat.style.display = "block";
      bottleFloat.style.left = "105%";
      bottleFloat.style.bottom = "18%";
      bottleFloat.style.opacity = "1";
      bottleFloat.style.transition = "none";
      // Force reflow
      void bottleFloat.offsetWidth;
      // Animate: float left across water surface, ~12s
      requestAnimationFrame(() => {
        bottleFloat.style.transition = "left 14s linear, bottom 3s ease-in-out, opacity 1s 13s";
        bottleFloat.style.left = "-15%";
        bottleFloat.style.bottom = "16%";
      });
      setTimeout(() => {
        if (bottleActive) {
          bottleFloat.style.opacity = "0";
          bottleActive = false;
        }
      }, 15000);
    };

    // 点击漂流瓶
    bottleFloat && (bottleFloat.onclick = () => {
      if (bottleCooldown) { showToast("漂流瓶刚被捡走，稍后再试！", ""); return; }
      if (!bottleActive) return;
      bottleActive = false;
      bottleFloat.style.opacity = "0";
      showBottlePanel();
    });

    const showBottlePanel = () => {
      if (!bottleContent) return;
      const mode = Math.random() > 0.5 ? "pick" : "throw";
      if (mode === "pick") {
        const msgs = ["愿你每一次抛竿都有收获 🍀", "山河远阔，渔者无界 🌊", "一竿山海，一渔人生 🎣", "钓到的都是风景 🐟", "愿鱼常伴，好运常在 ✨"];
        bottleContent.innerHTML = `
          <div style="font-size:60px;margin:12px 0">🍾</div>
          <div style="background:#f0f7ff;border-radius:12px;padding:16px;margin-bottom:12px">
            <div style="font-weight:600;margin-bottom:6px">💬 漂流瓶内容</div>
            <div style="font-size:14px;color:#555;line-height:1.7">${msgs[Math.floor(Math.random()*msgs.length)]}</div>
          </div>
          <div style="font-size:12px;color:#888;margin-bottom:12px">捡到漂流瓶，好运+1 🎉</div>
          <button class="btnOk primary" id="btnReplyBottle" style="width:100%">💬 回复漂流瓶</button>`;
        bottleContent.querySelector("#btnReplyBottle") && (bottleContent.querySelector("#btnReplyBottle").onclick = () => {
          const replies = ["也祝你大吉！🎣", "接好运！🍀", "一竿入海！🌊"];
          showToast(replies[Math.floor(Math.random()*replies.length)], "success");
          bottleCooldown = true;
          setTimeout(() => { bottleCooldown = false; spawnBottle(); }, 30000);
          closeMask(bottleMask);
        });
      } else {
        bottleContent.innerHTML = `
          <div style="font-size:60px;margin:12px 0">🍾</div>
          <div style="background:#fff8e1;border-radius:12px;padding:16px;margin-bottom:12px">
            <div style="font-weight:600;margin-bottom:6px">✍️ 写下一句话，放入大海</div>
            <input id="bottleMsg" placeholder="愿天下钓友常有好运…" style="width:100%;padding:8px;border-radius:8px;border:1px solid #ddd;font-size:13px;margin-bottom:8px">
          </div>
          <div style="font-size:12px;color:#888;margin-bottom:12px">扔出漂流瓶，与陌生人分享心情</div>
          <button class="btnOk primary" id="btnThrowBottle" style="width:100%">🚀 投放大海</button>`;
        bottleContent.querySelector("#btnThrowBottle") && (bottleContent.querySelector("#btnThrowBottle").onclick = () => {
          const msg = document.getElementById("bottleMsg")?.value || "愿天下钓友常有好运 🍀";
          showToast(`漂流瓶已投出：${msg.slice(0,10)}…`, "success");
          bottleCooldown = true;
          setTimeout(() => { bottleCooldown = false; spawnBottle(); }, 30000);
          closeMask(bottleMask);
        });
      }
      openMask(bottleMask);
    };

    btnBottleClose && (btnBottleClose.onclick = () => { closeMask(bottleMask); spawnBottle(); });

    // 每隔 45-90 秒随机出现漂流瓶
    setInterval(() => { if (Math.random() < 0.35) spawnBottle(); }, 45000);
    // 首次延迟出现
    setTimeout(() => spawnBottle(), 8000);

    // ══════════════════════════════════════════
    // 看广告（木牌广告 — 底部内嵌条，不弹遮罩）
    // ══════════════════════════════════════════
    const adSign = document.getElementById("adSign");
    const adBar = document.getElementById("adBar");
    const adbarTimer = document.getElementById("adbarTimer");
    const adbarFill = document.getElementById("adbarFill");
    const adbarSkip = document.getElementById("adbarSkip");

    let adPlaying = false;
    let adWatched = 0; // 今日已看次数
    let adInterval = null;

    adSign && (adSign.onclick = () => {
      if (adPlaying) { showToast("广告播放中，请稍候…", ""); return; }
      if (adWatched >= 10) { showToast("今日广告次数已用完（10次）", "error"); return; }
      playAd();
    });

    const playAd = () => {
      if (!adBar || !adbarTimer || !adbarFill) return;
      adPlaying = true;
      // 显示底部内嵌条
      adBar.style.display = "block";
      if (adbarTimer) adbarTimer.textContent = "10";
      if (adbarFill) adbarFill.style.width = "0%";
      if (adbarSkip) adbarSkip.style.display = "block";
      let remaining = 10;
      adInterval = setInterval(() => {
        remaining--;
        if (adbarTimer) adbarTimer.textContent = String(remaining);
        if (adbarFill) adbarFill.style.width = ((10 - remaining) / 10 * 100) + "%";
        if (remaining <= 0) {
          clearInterval(adInterval);
          adInterval = null;
          // 奖励！
          coinNum += 3;
          setText(coin, coinNum);
          adWatched++;
          adPlaying = false;
          showToast("📺 广告看完！+3💰", "success");
          if (adBar) adBar.style.display = "none";
          saveState();
        }
      }, 1000);
      adbarSkip && (adbarSkip.onclick = () => {
        if (adInterval) { clearInterval(adInterval); adInterval = null; }
        adPlaying = false;
        if (adBar) adBar.style.display = "none";
        showToast("广告已跳过，无奖励", "");
      });
    };
    btnArea && btnArea.addEventListener("click", () => { openMask(areaMask); renderAreaMenu(); });
    btnGoal && btnGoal.addEventListener("click", () => { openMask(goalMask); renderGoalPanel(); });
    const btnGoalClose = document.getElementById("btnGoalClose");
    btnGoalClose && btnGoalClose.addEventListener("click", () => closeMask(goalMask));
    btnDaily && btnDaily.addEventListener("click", () => { openMask(dailyMask); renderDailyPanel(); });
    const btnDailyClose2 = document.getElementById("btnDailyClose");
    btnDailyClose2 && btnDailyClose2.addEventListener("click", () => closeMask(dailyMask));
    // 📈成长 button (new 4-button layout)
    const btnGrowth = document.getElementById("btnGrowth");
    btnGrowth && btnGrowth.addEventListener("click", () => { openMask(goalMask); renderGoalPanel();
      // Show daily quests link inside goal panel
      setTimeout(() => {
        const goalC = document.getElementById("goalContent");
        if (goalC && !goalC.querySelector("[data-to-daily]")) {
          const el = document.createElement("div");
          el.style.cssText = "text-align:center;margin-top:12px";
          el.innerHTML = '<button class="miniBtn" data-to-daily="1">📋 查看每日任务 →</button>';
          el.querySelector("button").onclick = () => { openMask(dailyMask); renderDailyPanel(); };
          goalC.appendChild(el);
        }
      }, 100);
    });

    // Share card - Canvas poster
    const btnShare = document.getElementById("btnShare");
    btnShare && btnShare.addEventListener("click", () => {
      if (!lastRareCatch) return showToast("先钓一条稀有鱼再来分享吧!");
      generateSharePoster(lastRareCatch);
    });

    // system settings
    btnUpgradeRod && btnUpgradeRod.addEventListener("click", doUpgradeRod);
    btnSys && btnSys.addEventListener("click", () => sysMask && (sysMask.style.display = "flex"));
    btnSysClose && btnSysClose.addEventListener("click", () => sysMask && (sysMask.style.display = "none"));
    sysMask && sysMask.addEventListener("click", (e) => { if (e && e.target === sysMask) sysMask.style.display = "none"; });

    // 📱「更多」快速菜单（替代分散的多个按钮）
    const moreMenu = document.getElementById("moreMenu");
    const btnMore = document.getElementById("btnMore");
    let moreMenuVisible = false;
    const showMoreMenu = () => {
      moreMenuVisible = true;
      if (moreMenu) { moreMenu.style.display = "block"; }
    };
    const hideMoreMenu = () => {
      moreMenuVisible = false;
      if (moreMenu) { moreMenu.style.display = "none"; }
    };
    btnMore && btnMore.addEventListener("click", (e) => {
      e.stopPropagation();
      if (moreMenuVisible) { hideMoreMenu(); } else { showMoreMenu(); }
    });
    // 点击其他区域关闭菜单
    document.addEventListener("click", (e) => {
      if (moreMenuVisible && moreMenu && !moreMenu.contains(e.target) && e.target !== btnMore) {
        hideMoreMenu();
      }
    });
    // 更多菜单各项
    const btnMoreEmpire = document.getElementById("btnMoreEmpire");
    const btnMoreGrowth = document.getElementById("btnMoreGrowth");
    const btnMoreGoal = document.getElementById("btnMoreGoal");
    const btnMoreDaily = document.getElementById("btnMoreDaily");
    const btnMoreSys = document.getElementById("btnMoreSys");
    btnMoreEmpire && btnMoreEmpire.addEventListener("click", () => { hideMoreMenu(); openMask(empireMask); renderEmpirePanel(); });
    btnMoreGrowth && btnMoreGrowth.addEventListener("click", () => { hideMoreMenu(); openMask(goalMask); renderGoalPanel(); });
    btnMoreGoal && btnMoreGoal.addEventListener("click", () => { hideMoreMenu(); openMask(goalMask); renderGoalPanel(); });
    btnMoreDaily && btnMoreDaily.addEventListener("click", () => { hideMoreMenu(); openMask(dailyMask); renderDailyPanel(); });
    btnMoreSys && btnMoreSys.addEventListener("click", () => { hideMoreMenu(); sysMask && (sysMask.style.display = "flex"); });

    // ——— 以下保留旧按钮引用（防报错，DOM已移除但代码可能未清理）———
    // btnEmpire / btnGrowth / btnSys 在 actionBar 移除后不再被调用，保留以避免崩溃
    optSfx && optSfx.addEventListener("change", () => { setOpt(LS.sfx, optSfx.checked); applySys(); });
    optMotion && optMotion.addEventListener("change", () => { setOpt(LS.motion, optMotion.checked); applySys(); });
    optVibrate && optVibrate.addEventListener("change", () => { setOpt(LS.vibrate, optVibrate.checked); applySys(); });
    optNight && optNight.addEventListener("change", () => { setOpt(LS.night, optNight.checked); applySys(); });

    // logout - keep dev_key, can re-login to same account
    const btnLogout = document.getElementById("btnLogout");
    const btnLogoutAction = document.getElementById("btnLogoutAction");
    const btnResetAccount = document.getElementById("btnResetAccount");
    btnLogout && btnLogout.addEventListener("click", async () => {
      if (await customConfirm("退出后再次进入将自动回到同一账号。确定退出？")) {
        if (window.FisherAPI) window.FisherAPI.logout();
        location.reload();
      }
    });
    btnLogoutAction && btnLogoutAction.addEventListener("click", async () => {
      if (await customConfirm("退出后再次进入将自动回到同一账号。确定退出？")) {
        if (window.FisherAPI) window.FisherAPI.logout();
        location.reload();
      }
    });
    btnResetAccount && btnResetAccount.addEventListener("click", async () => {
      if (await customConfirm("⚠️ 这将清空所有本地记录并创建全新账号，不可恢复！确定？")) {
        if (window.FisherAPI) window.FisherAPI.resetAccount();
        location.reload();
      }
    });
    // Show logout button when logged in
    if (btnLogout && window.FisherAPI && window.FisherAPI.isLoggedIn) {
      btnLogout.style.display = "";
    }

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

  const boot = async () => {
    await loadState();
    // Skip age/role selection if already chosen (persisted)
    const hasAge = localStorage.getItem("fisher_age_chosen");
    const ageMask = document.getElementById("ageMask");
    const roleMask = document.getElementById("roleMask");
    const helpMask = document.getElementById("helpMask");
    if (!hasAge && ageMask) {
      ageMask.style.display = "flex";
      // Chain: age → role → help → game
      document.getElementById("btnAgeOk") && (document.getElementById("btnAgeOk").onclick = () => {
        localStorage.setItem("fisher_age_chosen", "1");
        ageMask.style.display = "none";
        if (roleMask) roleMask.style.display = "flex";
      });
      document.getElementById("btnRoleOk") && (document.getElementById("btnRoleOk").onclick = () => {
        if (roleMask) roleMask.style.display = "none";
        if (helpMask) helpMask.style.display = "flex";
      });
      document.getElementById("btnHelpOk") && (document.getElementById("btnHelpOk").onclick = () => {
        if (helpMask) helpMask.style.display = "none";
      });
    } else {
      // Already chosen, hide all masks
      if (ageMask) ageMask.style.display = "none";
      if (roleMask) roleMask.style.display = "none";
      if (helpMask) helpMask.style.display = "none";
    }
    buildRoleGrid();
    changeWeather("sunny");
    const initStyle = areaStyleById(curSpotId || 0);
    sceneDecor.innerHTML = initStyle.decor;
    applySys();
    refreshStorage();
    loadQuests();
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
    updateRoleBadgeFromAvatar();
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

