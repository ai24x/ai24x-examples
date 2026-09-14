/**
 * 山海渔 Fisher API 客户端
 * 支持 JWT 持久化（刷新不丢登录）、退出、注册预留。
 */
(() => {
  const API_BASE = "http://127.0.0.1:18041";

  const STORAGE_KEY_DEV = "fisher_dev_key";
  const STORAGE_KEY_TOKEN = "fisher_token";
  const STORAGE_KEY_NICK = "fisher_nickname";

  let _token = null;
  let _cachedSpots = null;
  let _cachedSpecies = null;

  /** 恢复缓存的 token */
  const _restoreToken = () => {
    if (_token) return true;
    try {
      const saved = localStorage.getItem(STORAGE_KEY_TOKEN);
      if (saved) {
        const parsed = JSON.parse(saved);
        // JWT token expires check (simple: check stored timestamp)
        if (parsed.token && parsed.expiresAt && Date.now() < parsed.expiresAt) {
          _token = parsed.token;
          return true;
        }
        // expired, clean up
        localStorage.removeItem(STORAGE_KEY_TOKEN);
      }
    } catch {}
    return false;
  };

  /** 持久化 token */
  const _persistToken = (token, expiresInDays = 7) => {
    _token = token;
    try {
      localStorage.setItem(STORAGE_KEY_TOKEN, JSON.stringify({
        token,
        expiresAt: Date.now() + expiresInDays * 86400 * 1000,
      }));
    } catch {}
  };

  const api = {
    /** 请求头 */
    _headers(contentType = false) {
      const h = {};
      if (contentType) h["Content-Type"] = "application/json";
      if (_token) h["Authorization"] = `Bearer ${_token}`;
      return h;
    },

    /** 统一请求 */
    async _req(method, path, body) {
      const opts = { method, headers: this._headers(!!body) };
      if (body) opts.body = JSON.stringify(body);
      const res = await fetch(`${API_BASE}${path}`, opts);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(typeof err.detail === "object" ? JSON.stringify(err.detail) : (err.detail || `HTTP ${res.status}`));
      }
      return res.json();
    },

    _get(path) { return this._req("GET", path); },
    _post(path, body) { return this._req("POST", path, body); },

    /** 检查是否有有效 token */
    get isLoggedIn() { return !!_token; },

    /** 获取当前昵称（本地缓存） */
    get nickname() {
      try { return localStorage.getItem(STORAGE_KEY_NICK) || ""; } catch { return ""; }
    },

    /**
     * 自动登录（优先恢复缓存 token，无效则重新登录）。
     * 开发模式：传入 dev_key 即自动创建/识别用户。
     */
    async autoLogin(devKey = "") {
      // 1. 尝试恢复缓存 token
      if (_restoreToken()) {
        try {
          // 验证 token 有效性
          await this.me();
          return { restored: true };
        } catch {
          // token 过期或无效，清除重新登录
          _token = null;
          localStorage.removeItem(STORAGE_KEY_TOKEN);
        }
      }

      // 2. 重新登录
      const key = devKey || localStorage.getItem(STORAGE_KEY_DEV) || this._generateDevKey();
      localStorage.setItem(STORAGE_KEY_DEV, key);
      const data = await this._post("/v1/auth/dev-login", { dev_key: key });
      _persistToken(data.access_token, data.expires_in_days || 7);
      if (!devKey) {
        try { localStorage.setItem(STORAGE_KEY_NICK, key.substring(0, 12)); } catch {}
      }
      return { restored: false, ...data };
    },

    /** 注册（预留：开发期 dev_key 即注册，后续对接微信 openid） */
    async register(nickname = "") {
      const key = nickname || prompt("请输入你的钓者名号（后续将关联微信）：", "渔客") || "渔客";
      localStorage.setItem(STORAGE_KEY_DEV, key);
      localStorage.setItem(STORAGE_KEY_NICK, key);
      return this.autoLogin(key);
    },

    /** 退出登录（保留 dev_key，重新登录可回到同一账号） */
    logout() {
      _token = null;
      _cachedSpots = null;
      _cachedSpecies = null;
      try {
        localStorage.removeItem(STORAGE_KEY_TOKEN);
        // 保留 STORAGE_KEY_DEV 和 STORAGE_KEY_NICK，重新登录时回到同一账号
      } catch {}
    },

    /** 彻底换号（清除所有本地数据） */
    resetAccount() {
      this.logout();
      try {
        localStorage.removeItem(STORAGE_KEY_DEV);
        localStorage.removeItem(STORAGE_KEY_NICK);
      } catch {}
    },

    /** 生成随机 dev_key */
    _generateDevKey() {
      const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
      let key = "user_";
      for (let i = 0; i < 8; i++) key += chars[Math.floor(Math.random() * chars.length)];
      return key;
    },

    /** 获取玩家状态 */
    async me() {
      return this._get("/v1/me");
    },

    /** 获取钓场列表（缓存） */
    async spots(force = false) {
      if (_cachedSpots && !force) return _cachedSpots;
      _cachedSpots = await this._get("/v1/catalog/spots");
      return _cachedSpots;
    },

    /** 获取鱼种列表（缓存，可选按 spot_id 过滤） */
    async species(spotId, force = false) {
      if (!_cachedSpecies || force) {
        const path = spotId != null ? `/v1/catalog/species?spot_id=${spotId}` : "/v1/catalog/species";
        _cachedSpecies = await this._get(path);
      }
      if (spotId != null) {
        return _cachedSpecies.filter(s => s.spot_id === spotId);
      }
      return _cachedSpecies;
    },

    /** 获取某钓场的鱼种池 */
    async speciesForSpot(spotId) {
      return this._get(`/v1/catalog/species?spot_id=${spotId}`);
    },

    /** 钓鱼 */
    async fish() {
      return this._post("/v1/game/fish", {});
    },

    /** 出售 */
    async sell(sellAll = false, speciesId = null, quantity = 1) {
      return this._post("/v1/game/sell", { sell_all: sellAll, species_id: speciesId, quantity: quantity });
    },

    /** 切换钓场 */
    async switchSpot(spotId) {
      return this._post("/v1/game/spot", { spot_id: spotId });
    },

    /** 获取token */
    get token() { return _token; },
  };

  window.FisherAPI = api;

  window.FisherConfig = {
    COMPLIANCE_MODE: true,
    APP_DESC: "垂钓社区与渔获管理工具",
  };
})();
