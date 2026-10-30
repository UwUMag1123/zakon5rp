/**
 * Интеграционный прогон index.html без браузера: поднимаем минимальный DOM,
 * исполняем настоящий скрипт страницы и проверяем, что она действительно
 * отрисовала базу, открыла документ и отработала поиск.
 *
 * Запуск: node tests/render.test.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const docs = JSON.parse(readFileSync(join(root, 'docs.json'), 'utf8'));

const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) throw new Error('не нашёл скрипт в index.html');
const script = scriptMatch[1];

/* ---------------- минимальный DOM ---------------- */

function makeClassList(el) {
  const set = new Set();
  return {
    add: (...c) => c.forEach(x => set.add(x)),
    remove: (...c) => c.forEach(x => set.delete(x)),
    contains: c => set.has(c),
    toggle: (c, force) => {
      const on = force === undefined ? !set.has(c) : !!force;
      on ? set.add(c) : set.delete(c);
      return on;
    },
    get _set() { return set; },
  };
}

function makeEl(id) {
  const el = {
    id,
    innerHTML: '',
    textContent: '',
    value: '',
    style: {},
    classList: null,
    listeners: {},
    attrs: {},
    children: [],
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    removeEventListener() {},
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k] ?? null; },
    removeAttribute(k) { delete this.attrs[k]; },
    focus() { document.activeElement = this; },
    blur() {},
    select() {},
    querySelectorAll() { return []; },
    querySelector() { return null; },
    appendChild() {},
    removeChild() {},
    scrollIntoView() {},
    dispatch(type, ev = {}) {
      (this.listeners[type] || []).forEach(fn => fn({ ...ev, target: this, preventDefault() {} }));
    },
  };
  el.classList = makeClassList(el);
  return el;
}

const elements = new Map();
const document = {
  activeElement: null,
  documentElement: makeEl('html'),
  body: makeEl('body'),
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, makeEl(id));
    return elements.get(id);
  },
  querySelectorAll() { return []; },
  querySelector() { return null; },
  addEventListener(type, fn) { (this._l = this._l || {})[type] = fn; },
  createElement() { return makeEl('tmp'); },
};

const location = {
  href: 'https://zakon5rp.pages.dev/',
  hash: '',
  replace(h) { const i = String(h).indexOf('#'); this.hash = i >= 0 ? String(h).slice(i) : ''; },
};
const history = {
  replaceState(_s, _t, url) { location.replace(url); },
};
const localStorage = {
  store: new Map(),
  getItem(k) { return this.store.has(k) ? this.store.get(k) : null; },
  setItem(k, v) { this.store.set(k, String(v)); },
};
const window = {
  _l: {},
  addEventListener(type, fn) { this._l[type] = fn; },
  scrollTo() {},
  location,
  history,
};
const fetchStub = (url) => {
  const name = String(url).replace(/^\.\//, '');
  if (name === 'docs.json') {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(JSON.stringify(docs))) });
  }
  return Promise.resolve({ ok: false, status: 404, json: () => Promise.reject(new Error('no')) });
};

/* ---------------- запуск ---------------- */

const run = new Function(
  'document', 'window', 'location', 'navigator', 'localStorage', 'history',
  'fetch', 'setTimeout', 'clearTimeout', 'console',
  script
);

let failed = 0;
let passed = 0;
function check(name, cond, extra) {
  if (cond) passed++;
  else { failed++; console.log('  FAIL ' + name + (extra ? '  → ' + extra : '')); }
}
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

console.log('— загрузка страницы —');
run(document, window, location, { clipboard: undefined }, localStorage, history, fetchStub, setTimeout, clearTimeout, console);
await sleep(80);

const railList = document.getElementById('railList');
const sheet = document.getElementById('sheet');
const searchInput = document.getElementById('searchInput');
const hitcount = document.getElementById('hitcount');
const promptBox = document.getElementById('promptBox');

check('список документов отрисован', (railList.innerHTML.match(/class="doclink/g) || []).length === docs.length,
  (railList.innerHTML.match(/class="doclink/g) || []).length + ' из ' + docs.length);
check('счётчик показал базу', /в базе/.test(hitcount.innerHTML), hitcount.innerHTML);
check('документ открылся по умолчанию', sheet.innerHTML.includes('doc-title') && sheet.innerHTML.includes('Конституция'));
check('появилась постоянная ссылка', sheet.innerHTML.includes('docs/codex-1.html'));
check('промпт заполнен', promptBox.value.length > 2000, 'длина ' + promptBox.value.length);
check('в промпте есть база', promptBox.value.includes('zakon5rp.pages.dev'));
check('подсветки нет без запроса', !sheet.innerHTML.includes('<mark>'));
check('статус «утратил силу» в списке', railList.innerHTML.includes('утратил силу'));

console.log('— поиск —');
searchInput.value = 'статья';
searchInput.dispatch('input');
await sleep(260);

const found = document.getElementById('hitcount').innerHTML;
const n = parseInt(found.replace(/<[^>]+>/g, ''), 10);
check('поиск вернул результаты', n > 5, found);
check('подсветка в документе появилась', sheet.innerHTML.includes('<mark>'), 'нет <mark>');
const marks = (sheet.innerHTML.match(/<mark>/g) || []).length;
check('подсветка множественная', marks > 3, marks + ' marks');

console.log('— сброс поиска —');
searchInput.value = '';
searchInput.dispatch('input');
await sleep(260);
check('подсветка снята', !sheet.innerHTML.includes('<mark>'));
check('счётчик вернулся к базе', /в базе/.test(document.getElementById('hitcount').innerHTML));

console.log('— переход по документу —');
location.hash = '#appeal-41';
window._l.hashchange();
await sleep(30);
check('открылся appeal-41', sheet.innerHTML.includes('appeal-41.html'), 'нет ссылки на appeal-41');

console.log('');
console.log(failed === 0 ? 'OK: ' + passed + ' проверок отрисовки пройдено' : failed + ' провалено, ' + passed + ' пройдено');
process.exit(failed === 0 ? 0 : 1);
