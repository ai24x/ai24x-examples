// utils/store.js — 本地存档（v1 原型：段位/累计积分/最高分/历史全部本地判定）
const KEY_BEST = 'p01_best_score';
const KEY_CUM = 'p01_cum_score';
const KEY_GAMES = 'p01_total_games';
const KEY_HISTORY = 'p01_history';
const KEY_DAILY = 'p01_daily_done';
const MAX_HISTORY = 20;

function get(key, def) {
  try {
    const v = wx.getStorageSync(key);
    return v === '' || v === null || v === undefined ? def : v;
  } catch (e) {
    return def;
  }
}

function set(key, val) {
  try { wx.setStorageSync(key, val); } catch (e) {}
}

function ensure() {
  if (get(KEY_BEST, null) === null) {
    set(KEY_BEST, 0);
    set(KEY_CUM, 0);
    set(KEY_GAMES, 0);
    set(KEY_HISTORY, []);
  }
}

function pad(n) {
  return n < 10 ? '0' + n : '' + n;
}

function todayStr() {
  const d = new Date();
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

// 保存一局结果，返回 { best, cum, games, isNewBest }
function saveRound(round) {
  ensure();
  const prevBest = get(KEY_BEST, 0);
  const best = Math.max(prevBest, round.score);
  const cum = get(KEY_CUM, 0) + round.score;
  const games = get(KEY_GAMES, 0) + 1;
  const history = get(KEY_HISTORY, []);
  const entry = Object.assign({ date: todayStr(), ts: Date.now() }, round);
  history.unshift(entry);
  if (history.length > MAX_HISTORY) history.length = MAX_HISTORY;
  set(KEY_BEST, best);
  set(KEY_CUM, cum);
  set(KEY_GAMES, games);
  set(KEY_HISTORY, history);
  if (round.daily) {
    set(KEY_DAILY, { date: round.dailyDate || todayStr(), score: round.score, ts: Date.now() });
  }
  return {
    best: best,
    cum: cum,
    games: games,
    isNewBest: round.score === best && round.score > 0
  };
}

function getBest() { return get(KEY_BEST, 0); }
function getCum() { return get(KEY_CUM, 0); }
function getGames() { return get(KEY_GAMES, 0); }
function getHistory() { return get(KEY_HISTORY, []); }
function getDailyDone() { return get(KEY_DAILY, null); }

// 本地最高分榜（按日取最高，原型用；v2 换中台好友关系链）
function localLeaderboard() {
  const hist = getHistory();
  const byDate = {};
  hist.forEach(function (r) {
    if (!byDate[r.date] || r.score > byDate[r.date]) byDate[r.date] = r.score;
  });
  return Object.keys(byDate)
    .map(function (date) { return { date: date, score: byDate[date] }; })
    .sort(function (a, b) { return b.score - a.score; })
    .slice(0, 5);
}

module.exports = {
  ensure: ensure,
  saveRound: saveRound,
  getBest: getBest,
  getCum: getCum,
  getGames: getGames,
  getHistory: getHistory,
  getDailyDone: getDailyDone,
  localLeaderboard: localLeaderboard,
  todayStr: todayStr
};