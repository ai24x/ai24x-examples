// 交互级冒烟：DOM stub + vm 执行游戏脚本，模拟点击/答题/帧循环，抓运行时异常
const fs = require('fs');
const vm = require('vm');
const dir = 'C:/Users/Administrator/ops/gameweb';
let fail = 0;

function makeEnv(canvasH) {
  const els = {}, handlers = {}, timers = [], rafCbs = [];
  function el(id) {
    if (els[id]) return els[id];
    const e = {
      id, _text: '', _html: '', _children: [], className: '', dataset: {},
      style: {}, tagName: 'DIV',
      classList: {
        _s: new Set(),
        add(...c) { c.forEach(x => this._s.add(x)); },
        remove(...c) { c.forEach(x => this._s.delete(x)); },
        toggle(c, f) { f === undefined ? (this._s.has(c) ? this._s.delete(c) : this._s.add(c)) : (f ? this._s.add(c) : this._s.delete(c)); },
        contains(c) { return this._s.has(c); }
      },
      get textContent() { return this._text; }, set textContent(v) { this._text = v; },
      get innerHTML() { return this._html; }, set innerHTML(v) { this._html = v; this._children.length = 0; },
      get children() { return this._children; },
      appendChild(c) { this._children.push(c); return c; },
      addEventListener(t, fn) { (handlers[id] = handlers[id] || {})[t] = fn; },
      setPointerCapture() {}, setAttribute() {}, removeAttribute() {},
      getBoundingClientRect() { return { left: 0, top: 0, width: 390, height: canvasH || 560 }; },
      getContext() { return ctx; },
      get width() { return 390; }, set width(v) {}, get height() { return canvasH || 560; }, set height(v) {}
    };
    els[id] = e; return e;
  }
  const ctx = {
    fillStyle: '', strokeStyle: '', lineWidth: 1, font: '', textAlign: '', textBaseline: '',
    scale() {}, clearRect() {}, fillRect() {}, strokeRect() {}, beginPath() {}, moveTo() {},
    arcTo() {}, closePath() {}, fill() {}, stroke() {}, fillText() {}
  };
  const document = {
    getElementById: id => el(id),
    createElement: tag => { const e = el('__' + tag + '_' + (Object.keys(els).length)); e.tagName = tag; return e; },
    addEventListener() {}, documentElement: {}
  };
  const sandbox = {
    document, console, Math, JSON, Date, isNaN, parseFloat, parseInt, Number, String, Boolean, Array, Object,
    innerWidth: 390, innerHeight: 780, devicePixelRatio: 1,
    localStorage: { getItem: () => null, setItem() {} },
    addEventListener(type, fn) { (handlers['__window'] = handlers['__window'] || {})[type] = fn; },
    requestAnimationFrame: fn => { rafCbs.push(fn); return rafCbs.length; },
    performance: { now: () => 0 },
    setTimeout: (fn) => { timers.push({ fn }); return timers.length; },
    clearTimeout() {},
    PointerEvent: function () {}
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  return { sandbox, els, handlers, timers, rafCbs };
}
function fire(env, id, type, evt) {
  const fn = (env.handlers[id] || {})[type];
  if (!fn) throw new Error('no handler ' + id + '.' + type);
  fn.call(env.els[id], Object.assign({ preventDefault() {}, pointerId: 1, stopPropagation() {} }, evt || {}));
}
function drainOne(env) { const t = env.timers.shift(); if (!t) throw new Error('no pending timer'); t.fn(); }
const runs = [];
function run(name, fn) {
  try { fn(); runs.push(name + ': PASS'); }
  catch (e) { fail = 1; runs.push(name + ': FAIL ' + e.message); console.log(name, 'ERROR:', e.stack ? e.stack.split('\n').slice(1, 4).join(' | ') : e.message); }
}

// ---------- color-sort ----------
run('color-sort interaction', () => {
  const html = fs.readFileSync(dir + '/color-sort.html', 'utf8');
  const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const env = makeEnv(540);
  vm.runInContext(code, env.sandbox);
  const mv = env.els['mv'].textContent;
  if (+mv !== 0) throw new Error('initial moves != 0: ' + mv);
  fire(env, 'stage', 'pointerdown', { clientX: 70, clientY: 300 });   // select tube 0
  fire(env, 'stage', 'pointerdown', { clientX: 120, clientY: 300 });  // pour into tube 1 (or switch)
  fire(env, 'stage', 'pointerdown', { clientX: 70, clientY: 100 });   // miss area -> deselect
  fire(env, 'undoBtn', 'pointerdown', {});
  fire(env, 'resetBtn', 'pointerdown', {});
  fire(env, 'restart', 'pointerdown', {});
  fire(env, 'restartAll', 'pointerdown', {});
});

// ---------- trivia-duel ----------
run('trivia-duel full match', () => {
  const html = fs.readFileSync(dir + '/trivia-duel.html', 'utf8');
  const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const env = makeEnv(0);
  env.sandbox.document.getElementById('overlay').classList.add('show'); // HTML 初始 class="show"（intro）
  vm.runInContext(code, env.sandbox);
  const overlay = env.els['overlay'];
  if (!overlay.classList.contains('show')) throw new Error('intro overlay not shown at load');
  fire(env, 'playBtn', 'pointerdown', {});
  if (overlay.classList.contains('show')) throw new Error('overlay still shown after begin');
  const answerOne = () => {
    const btns = env.els['opts'].children;
    if (btns.length !== 4) throw new Error('expected 4 options, got ' + btns.length);
    fire(env, btns[0].id, 'pointerdown', {});   // always pick option A
    drainOne(env);                          // 1100ms feedback -> next
  };
  for (let i = 0; i < 4; i++) answerOne();  // A: Q1-4
  answerOne();                              // A: Q5 -> showTurn 计时器挂起
  if (!env.els['turn'].classList.contains('show')) throw new Error('turn banner not shown after A');
  drainOne(env);                            // 1200ms -> 轮到 B
  if (env.els['who'].textContent.indexOf('玩家 B') < 0) throw new Error('not player B turn: ' + env.els['who'].textContent);
  for (let i = 0; i < 4; i++) answerOne();  // B: Q1-4
  answerOne();                              // B: Q5 -> 结算
  if (!overlay.classList.contains('show')) throw new Error('result overlay not shown');
  const t = env.els['ovT'].textContent;
  if (!/获胜|平手/.test(t)) throw new Error('bad result title: ' + t);
  if (!/玩家 A/.test(env.els['ovS'].textContent)) throw new Error('bad score line: ' + env.els['ovS'].textContent);
  if (!/历史最佳/.test(env.els['bestLine'].textContent)) throw new Error('bad best line');
});

// ---------- dodge-dash ----------
run('dodge-dash frames', () => {
  const html = fs.readFileSync(dir + '/dodge-dash.html', 'utf8');
  const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const env = makeEnv(560);
  vm.runInContext(code, env.sandbox);
  if (env.els['tm'].textContent !== '0.0') throw new Error('init time != 0.0');
  fire(env, 'stage', 'pointerdown', { clientX: 300, clientY: 300, pointerId: 7 });  // hold right half
  fire(env, 'stage', 'pointermove', { clientX: 60, clientY: 300, pointerId: 7 });  // slide to left half
  for (let f = 0; f < 120; f++) { const cb = env.rafCbs[env.rafCbs.length - 1]; cb(f * 16.7); }
  const t = parseFloat(env.els['tm'].textContent);
  if (!(t > 0.5)) throw new Error('timer did not advance: ' + t);
  fire(env, '__window', 'pointerup', { pointerId: 7 });
  fire(env, 'restart', 'pointerdown', {});
  if (env.els['tm'].textContent !== '0.0') throw new Error('restart did not reset timer');
});

console.log(runs.join('\n'));
console.log(fail ? 'RESULT: FAIL' : 'RESULT: PASS');
process.exit(fail);
