(() => {
  const $ = (id) => document.getElementById(id);

  const LS = {
    state: "ai24x_fisher_demo2_state_v1",
  };

  const isDev = () => {
    try {
      const u = new URL(location.href);
      return u.searchParams.get("dev") === "1";
    } catch {
      return false;
    }
  };

  const fishIconSrc = (id) => `../assets/fish/${encodeURIComponent(String(id))}.svg`;

  const load = () => {
    try {
      const raw = localStorage.getItem(LS.state);
      if (!raw) return { coinNum: 200, scoreNum: 0, fishBag: {}, items: {} };
      const s = JSON.parse(raw);
      return {
        coinNum: Number(s.coinNum || 0),
        scoreNum: Number(s.scoreNum || 0),
        fishBag: (s.fishBag && typeof s.fishBag === "object") ? s.fishBag : {},
        items: (s.items && typeof s.items === "object") ? s.items : {},
      };
    } catch {
      return { coinNum: 200, scoreNum: 0, fishBag: {}, items: {} };
    }
  };

  const save = (s) => {
    localStorage.setItem(LS.state, JSON.stringify(s));
  };

  const calcRecycle = (base) => {
    const b = Math.max(1, Number(base || 1));
    return Math.max(1, Math.floor(b * 0.8));
  };

  const render = () => {
    const s = load();
    const fishBag = s.fishBag || {};

    const names = Object.keys(fishBag).filter((k) => fishBag[k] && fishBag[k].num > 0);
    let total = 0;
    for (const nm of names) total += Number(fishBag[nm].num || 0);

    const coin = $("coin");
    const score = $("score");
    const kinds = $("kinds");
    const totalEl = $("total");
    if (coin) coin.textContent = String(s.coinNum || 0);
    if (score) score.textContent = String(s.scoreNum || 0);
    if (kinds) kinds.textContent = String(names.length);
    if (totalEl) totalEl.textContent = String(total);

    const list = $("list");
    if (!list) return;
    list.innerHTML = "";

    if (!names.length) {
      const empty = document.createElement("div");
      empty.className = "bagRow";
      empty.innerHTML = `<div class="bagL"><div><div class="bagNm">暂无鱼获</div><div class="bagMeta">去主界面抛竿钓几条鱼吧</div></div></div>`;
      list.appendChild(empty);
      return;
    }

    names
      .sort((a, b) => a.localeCompare(b, "zh-CN"))
      .forEach((nm) => {
        const f = fishBag[nm];
        const base = Number(f.coin || 1);
        const recycle = calcRecycle(base);

        const row = document.createElement("div");
        row.className = "bagRow";
        row.innerHTML = `
          <div class="bagL">
            <img alt="${nm}" src="${fishIconSrc(f.id)}" />
            <div style="min-width:0">
              <div class="bagNm">${nm}</div>
              <div class="bagMeta">持有 ${f.num} · 回收价 ${recycle}/条（基准 ${base}）</div>
            </div>
          </div>
          <div class="bagR">
            <button class="miniBtn" data-sell1="${encodeURIComponent(nm)}">回收1条</button>
            <button class="miniBtn primary" data-sellall="${encodeURIComponent(nm)}">回收全部</button>
          </div>
        `;
        list.appendChild(row);
      });
  };

  const sell1 = (nm) => {
    const s = load();
    const fishBag = s.fishBag || {};
    const f = fishBag[nm];
    if (!f || f.num <= 0) return;
    const price = Math.max(1, Math.floor(Number(f.coin || 1) * 0.8));
    f.num -= 1;
    s.coinNum = Number(s.coinNum || 0) + price;
    save(s);
    render();
  };

  const sellAllFish = (nm) => {
    const s = load();
    const fishBag = s.fishBag || {};
    const f = fishBag[nm];
    if (!f || f.num <= 0) return;
    const num = Number(f.num || 0);
    const price = Math.max(1, Math.floor(Number(f.coin || 1) * 0.8));
    f.num = 0;
    s.coinNum = Number(s.coinNum || 0) + price * num;
    save(s);
    render();
  };

  const sellAll = () => {
    const s = load();
    const fishBag = s.fishBag || {};
    let gain = 0;
    Object.keys(fishBag).forEach((nm) => {
      const f = fishBag[nm];
      if (!f || f.num <= 0) return;
      const num = Number(f.num || 0);
      const price = Math.max(1, Math.floor(Number(f.coin || 1) * 0.8));
      gain += price * num;
      f.num = 0;
    });
    s.coinNum = Number(s.coinNum || 0) + gain;
    save(s);
    render();
  };

  const reset = () => {
    // Dev-only: never expose to players by default
    if (!isDev()) return;
    const ok = confirm("仅开发调试：确定清空本地存档？这会重置金币/库存等。");
    if (!ok) return;
    localStorage.removeItem(LS.state);
    render();
  };

  document.addEventListener("click", (e) => {
    const t = e.target;
    if (!t) return;
    const back = t.closest && t.closest("#btnBack");
    if (back) { location.href = "index.html"; return; }
    const sell1Btn = t.closest && t.closest("[data-sell1]");
    if (sell1Btn) { sell1(decodeURIComponent(sell1Btn.getAttribute("data-sell1"))); return; }
    const sellAllBtn = t.closest && t.closest("[data-sellall]");
    if (sellAllBtn) { sellAllFish(decodeURIComponent(sellAllBtn.getAttribute("data-sellall"))); return; }
    const sellAll2 = t.closest && t.closest("#btnSellAll");
    if (sellAll2) {
      const ok = confirm("确认将仓库里的鱼获全部回收为金币？");
      if (!ok) return;
      sellAll();
      return;
    }
    const resetBtn = t.closest && t.closest("#btnReset");
    if (resetBtn) { reset(); return; }
  });

  render();
})();

