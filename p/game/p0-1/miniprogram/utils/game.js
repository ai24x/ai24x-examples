// utils/game.js — 别听它的 · 游戏核心逻辑（纯函数，无小程序 API 依赖，可直接单测）
// 计分/连击/难度曲线与 H5 原型完全一致，另增：双倍积分、每日挑战同种子序列

const DURATION = 45;          // 一局秒数
const LIFE_BONUS = 15;        // 看视频续命秒数
const BASE_GAIN = 10;         // 基础每题得分
const MAX_MULT = 5;           // 连击倍率封顶

const RANKS = [
  { name: '青铜', min: 0 },
  { name: '白银', min: 1500 },
  { name: '黄金', min: 4000 },
  { name: '铂金', min: 8000 },
  { name: '钻石', min: 14000 },
  { name: '星耀', min: 22000 },
  { name: '王者', min: 32000 }
];

const COLORS = [
  { k: 'red', label: '红', hex: '#ef4444', cls: 'red' },
  { k: 'green', label: '绿', hex: '#22c55e', cls: 'green' },
  { k: 'blue', label: '蓝', hex: '#3b82f6', cls: 'blue' }
];

const DIRS = [
  { k: 'left', label: '←' },
  { k: 'right', label: '→' },
  { k: 'up', label: '↑' },
  { k: 'down', label: '↓' }
];

const NUM_BUTTONS = [1, 2, 3, 4, 5, 6].map(function (x) {
  return { k: String(x), label: String(x) };
});

// ---------- 随机数（可复现，供每日挑战同种子固定序列） ----------
function hashStr(s) {
  let h = 1779033703 ^ s.length;
  for (let i = 0; i < s.length; i++) {
    h = Math.imul(h ^ s.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return h >>> 0;
}

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function seedForDate(dateStr) {
  return hashStr('p01-daily:' + dateStr);
}

function pick(rng, arr) {
  return arr[Math.floor(rng() * arr.length)];
}

function pickExcept(rng, arr, exceptKey) {
  const rest = arr.filter(function (x) { return x.k !== exceptKey; });
  return pick(rng, rest);
}

// ---------- 指令生成（3 种，随机切换） ----------
function buildColorTask(rng) {
  // 说「点X」→ 点反色；字色用答案色显示（Stroop：字义与颜色冲突）
  const target = pick(rng, COLORS);              // 正确答案颜色
  const word = pickExcept(rng, COLORS, target.k); // 显示的字（陷阱）
  return {
    type: 'color',
    main: '点【' + word.label + '】',
    mainColor: target.hex,
    sub: '按字义做相反',
    pad: 'colors',
    buttons: COLORS.map(function (c) { return { k: c.k, label: c.label, cls: c.cls }; }),
    correct: target.k,
    hint: '说点' + word.label + ' → 点' + target.label
  };
}

function buildDirTask(rng) {
  const shown = pick(rng, DIRS);
  const correct = pickExcept(rng, DIRS, shown.k);
  return {
    type: 'dir',
    main: shown.label,
    mainColor: '#ffffff',
    sub: '按相反方向',
    pad: 'dirs',
    buttons: DIRS.map(function (d) { return { k: d.k, label: d.label, cls: 'arrow' }; }),
    correct: correct.k,
    hint: '显示' + shown.label + ' → 按' + correct.label
  };
}

function buildNumTask(rng) {
  const n = 2 + Math.floor(rng() * 4); // 2..5
  const correct = n + 1;
  return {
    type: 'num',
    main: String(n),
    mainColor: '#ffffff',
    sub: '按 N+1',
    pad: 'nums',
    buttons: NUM_BUTTONS.map(function (x) {
      return { k: x.k, label: x.label, cls: 'gray' };
    }),
    correct: String(correct),
    hint: '显示' + n + ' → 按' + correct
  };
}

function buildPrompt(rng) {
  const t = Math.floor(rng() * 3);
  if (t === 0) return buildColorTask(rng);
  if (t === 1) return buildDirTask(rng);
  return buildNumTask(rng);
}

// ---------- 计分 / 段位 ----------
function comboMult(combo) {
  return Math.min(MAX_MULT, 1 + Math.floor(combo / 10));
}

function gainFor(combo, doubled) {
  const g = BASE_GAIN * comboMult(combo);
  return doubled ? g * 2 : g;
}

function intervalFor(combo) {
  return Math.max(700, 1500 - Math.floor(combo / 5) * 40);
}

function rankOf(score) {
  let r = RANKS[0];
  for (let i = 0; i < RANKS.length; i++) {
    if (score >= RANKS[i].min) r = RANKS[i];
  }
  return r;
}

function beatPct(score) {
  return Math.min(99, Math.round(40 + score / 60));
}

module.exports = {
  DURATION: DURATION,
  LIFE_BONUS: LIFE_BONUS,
  BASE_GAIN: BASE_GAIN,
  MAX_MULT: MAX_MULT,
  RANKS: RANKS,
  COLORS: COLORS,
  DIRS: DIRS,
  NUM_BUTTONS: NUM_BUTTONS,
  buildPrompt: buildPrompt,
  buildColorTask: buildColorTask,
  buildDirTask: buildDirTask,
  buildNumTask: buildNumTask,
  comboMult: comboMult,
  gainFor: gainFor,
  intervalFor: intervalFor,
  rankOf: rankOf,
  beatPct: beatPct,
  seedForDate: seedForDate,
  mulberry32: mulberry32,
  hashStr: hashStr
};