const app = getApp()

function api(path, method, data) {
  return new Promise((resolve, reject) => {
    const token = app.globalData.token
    const header = { "content-type": "application/json" }
    if (token) header.Authorization = `Bearer ${token}`
    wx.request({
      url: `${app.globalData.apiBase}${path}`,
      method,
      data: data || {},
      header,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data)
        else reject(res)
      },
      fail: reject,
    })
  })
}

Page({
  data: {
    coins: 0,
    score: 0,
    loading: false,
    lastFish: "",
    biteFlash: false,
    wave: false,
    // phases: idle -> waiting -> bite -> cooldown
    phase: "idle",
    phaseText: "空闲",
    hintText: "点击「抛竿」开始",
    showPull: false,
    castDisabled: false,
    pullDisabled: true,
  },

  _biteTimer: null,
  _cooldownTimer: null,
  _cooldownRemainS: 0,

  async onLoad() {
    await this.ensureToken()
    await this.refreshMe()
    this._setPhase("idle", "点击「抛竿」开始")
  },

  onUnload() {
    this._clearTimers()
  },

  _clearTimers() {
    if (this._biteTimer) {
      clearTimeout(this._biteTimer)
      this._biteTimer = null
    }
    if (this._cooldownTimer) {
      clearInterval(this._cooldownTimer)
      this._cooldownTimer = null
    }
  },

  _setPhase(phase, hintText) {
    const map = { idle: "空闲", waiting: "等待咬钩", bite: "已咬钩", cooldown: "冷却中" }
    const phaseText = map[phase] || phase
    const showPull = phase === "bite"
    const castDisabled = phase !== "idle"
    const pullDisabled = phase !== "bite"
    this.setData({
      phase,
      phaseText,
      hintText: hintText || "",
      showPull,
      castDisabled,
      pullDisabled,
    })
  },

  _startWave() {
    this.setData({ wave: true })
    setTimeout(() => this.setData({ wave: false }), 1100)
  },

  _startCooldown(seconds) {
    const s0 = Math.max(0, parseInt(seconds || 0, 10))
    this._cooldownRemainS = s0
    if (s0 <= 0) {
      this._setPhase("idle", "点击「抛竿」开始")
      return
    }
    this._setPhase("cooldown", `冷却中 ${this._cooldownRemainS}s`)
    if (this._cooldownTimer) clearInterval(this._cooldownTimer)
    this._cooldownTimer = setInterval(() => {
      this._cooldownRemainS = Math.max(0, this._cooldownRemainS - 1)
      if (this._cooldownRemainS <= 0) {
        clearInterval(this._cooldownTimer)
        this._cooldownTimer = null
        this._setPhase("idle", "点击「抛竿」开始")
        return
      }
      this.setData({ hintText: `冷却中 ${this._cooldownRemainS}s` })
    }, 1000)
  },

  async ensureToken() {
    try {
      const out = await api("/v1/auth/dev-login", "POST", { dev_key: app.globalData.devKey })
      app.globalData.token = out.access_token
    } catch (e) {
      wx.showToast({ title: "登录 API 失败", icon: "none" })
    }
  },

  async refreshMe() {
    try {
      const me = await api("/v1/me", "GET")
      this.setData({ coins: me.coins, score: me.score })
    } catch (e) {
      wx.showToast({ title: "拉取状态失败", icon: "none" })
    }
  },

  async onCast() {
    if (this.data.phase !== "idle") return
    this._clearTimers()
    this._startWave()
    this.setData({ biteFlash: false })
    this._setPhase("waiting", "已抛竿，静待鱼讯…")

    // Local wait to create “手感”；真正渔获由服务端在收竿时结算
    const waitMs = 1500 + Math.floor(Math.random() * 2200)
    this._biteTimer = setTimeout(() => {
      this._biteTimer = null
      this.setData({ biteFlash: true })
      wx.vibrateShort({ type: "heavy" })
      this._setPhase("bite", "鱼已咬钩！点击「收竿」")
    }, waitMs)
  },

  async onPull() {
    if (this.data.phase !== "bite") return
    this._clearTimers()
    this.setData({ loading: true, biteFlash: false })
    this._startWave()
    this._setPhase("cooldown", "收竿中…")
    try {
      const r = await api("/v1/game/fish", "POST", {})
      this.setData({
        lastFish: `${r.name}（${r.currency === "coin" ? "可卖金币" : "积分鱼"}）`,
      })
      wx.vibrateShort({ type: "medium" })
      await this.refreshMe()
      this._startCooldown(r.cooldown_s || 8)
    } catch (e) {
      const d = e && e.data ? e.data.detail : null
      const msg = d && d.retry_after_s != null ? `冷却中 ${d.retry_after_s}s` : "收竿失败"
      wx.showToast({ title: msg, icon: "none" })
      if (d && d.retry_after_s != null) this._startCooldown(d.retry_after_s)
      else this._setPhase("idle", "点击「抛竿」开始")
    } finally {
      this.setData({ loading: false })
    }
  },

  async onSellAll() {
    this.setData({ loading: true })
    try {
      const r = await api("/v1/game/sell", "POST", { sell_all: true })
      wx.showToast({
        title: r.coins_delta ? `金币+${r.coins_delta}` : r.score_delta ? `积分+${r.score_delta}` : "无可售",
        icon: "none",
      })
      await this.refreshMe()
    } catch (e) {
      wx.showToast({ title: "出售失败", icon: "none" })
    } finally {
      this.setData({ loading: false })
    }
  },
})
