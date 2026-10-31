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
  if (name === 'search-index.json') {
    const raw = readFileSync(join(root, 'search-index.json'), 'utf8');
    return Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(raw)) });
  }
  if (name === 'uak-articles.json') {
    const raw = readFileSync(join(root, 'uak-articles.json'), 'utf8');
    return Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(raw)) });
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
check('на главной — обложка со статистикой', sheet.innerHTML.includes('class="hero"') && sheet.innerHTML.includes('class="stats"'));
check('обложка показывает число документов', /\d+ (документ|документа|документов)/.test(sheet.innerHTML));
check('промпт заполнен', promptBox.value.length > 2000, 'длина ' + promptBox.value.length);
check('в промпте есть база', promptBox.value.includes('zakon5rp.pages.dev'));
check('статус «утратил силу» в списке', railList.innerHTML.includes('утратил силу'));

console.log('— открытие документа —');
location.hash = '#codex-1';
window._l.hashchange();
await sleep(60);
check('документ открылся по ссылке', sheet.innerHTML.includes('doc-title') && sheet.innerHTML.includes('Конституция'));
check('есть постоянная ссылка', sheet.innerHTML.includes('docs/codex-1.html'));
check('есть порядковый номер', /doc-index/.test(sheet.innerHTML));
check('подсветки нет без запроса', !sheet.innerHTML.includes('<mark>'));

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

console.log('— ссылки на статьи в тексте —');
location.hash = '#codex-2';
window._l.hashchange();
await sleep(60);
const arefs = (sheet.innerHTML.match(/class="aref"/g) || []).length;
check('в тексте УАК появились ссылки на статьи', arefs > 0, arefs + ' ссылок');
check('ссылка ведёт на страницу статьи', /href="docs\/uak\/[\d.]+\.html"/.test(sheet.innerHTML));

console.log('— палитра —');
document._l.keydown({ key: 'k', ctrlKey: true, target: { tagName: 'BODY' }, preventDefault() {} });
await sleep(120);
const palette = document.getElementById('palette');
const palList = document.getElementById('palList');
const palInput = document.getElementById('palInput');
check('Ctrl+K открыл палитру', palette.classList.contains('open'));
check('палитра заполнилась', palList.innerHTML.length > 50, 'длина ' + palList.innerHTML.length);
check('в палитре есть действия', palList.innerHTML.includes('Действия'));

palInput.value = '12.8';
palInput.dispatch('input');
await sleep(40);
const plainPal = palList.innerHTML.replace(/<[^>]+>/g, '');
check('поиск по номеру нашёл статью', /Ст\. 12\.8 УАК/.test(plainPal), plainPal.slice(0, 120));

palInput.value = 'жетон';
palInput.dispatch('input');
await sleep(40);
check('поиск по слову нашёл методичку', /method-1[01]/.test(palList.innerHTML) || palList.innerHTML.includes('жетон'),
  palList.innerHTML.slice(0, 160));

palInput.value = '12.8';
palInput.dispatch('input');
await sleep(40);
palInput.dispatch('keydown', { key: 'Enter', preventDefault() {} });
await sleep(40);
check('Enter увёл на страницу статьи', /docs\/uak\/12\.8\.html$/.test(location.href), location.href);
check('палитра закрылась', !palette.classList.contains('open'));

console.log('');
console.log(failed === 0 ? 'OK: ' + passed + ' проверок отрисовки пройдено' : failed + ' провалено, ' + passed + ' пройдено');
process.exit(failed === 0 ? 0 : 1);
