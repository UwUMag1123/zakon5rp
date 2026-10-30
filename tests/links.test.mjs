/**
 * Проверка внутренних ссылок: всё, на что ссылаются страницы, должно существовать
 * в репозитории. Ловит опечатки в id и забытые сгенерированные страницы.
 *
 * Запуск: node tests/links.test.mjs
 */
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, normalize } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

let failed = 0;
let checked = 0;
const problems = [];

const docs = JSON.parse(readFileSync(join(root, 'docs.json'), 'utf8'));
const ids = new Set(docs.map(d => d.id));

function localTargets(html) {
  const out = [];
  const re = /(?:href|src)\s*=\s*"([^"]*)"/gi;
  let m;
  while ((m = re.exec(html))) {
    let url = m[1].trim();
    if (!url) continue;
    if (/^(https?:|mailto:|tel:|data:|javascript:|\/\/)/i.test(url)) continue;
    if (url === '#') continue;
    out.push(url);
  }
  return out;
}

function checkFile(relPath) {
  const full = join(root, relPath);
  // из <script> ссылки собираются конкатенацией строк — их проверять бессмысленно
  const html = readFileSync(full, 'utf8').replace(/<script[\s\S]*?<\/script>/gi, '');
  const baseDir = dirname(full);
  for (const url of localTargets(html)) {
    const clean = url.split('#')[0].split('?')[0];
    if (!clean) continue; // чистая ссылка-якорь
    checked++;
    const target = normalize(join(baseDir, decodeURIComponent(clean)));
    if (!existsSync(target)) {
      problems.push(relPath + ' → ' + url + ' (нет файла)');
      continue;
    }
    if (clean.startsWith('docs/') && clean.endsWith('.html') && !clean.endsWith('index.html')) {
      const id = clean.slice('docs/'.length, -'.html'.length);
      if (!ids.has(id)) problems.push(relPath + ' → ' + url + ' (id отсутствует в docs.json)');
    }
  }
}

checkFile('index.html');
checkFile('docs/index.html');
checkFile('404.html');

for (const f of readdirSync(join(root, 'docs'), { withFileTypes: true })) {
  if (f.isDirectory()) {
    for (const g of readdirSync(join(root, 'docs', f.name))) {
      if (g.endsWith('.html')) checkFile(join('docs', f.name, g));
    }
  } else if (f.name.endsWith('.html') && f.name !== 'index.html') {
    checkFile(join('docs', f.name));
  }
}

// каждая запись docs.json обязана иметь свою страницу
for (const id of ids) {
  if (!existsSync(join(root, 'docs', id + '.html'))) {
    problems.push('docs.json: для id ' + id + ' нет docs/' + id + '.html');
  }
}

if (problems.length) {
  failed = problems.length;
  for (const p of problems.slice(0, 40)) console.log('  - ' + p);
  if (problems.length > 40) console.log('  … и ещё ' + (problems.length - 40));
}

console.log('');
console.log(
  failed === 0
    ? 'OK: ' + checked + ' внутренних ссылок, ' + ids.size + ' документов — всё на месте'
    : failed + ' проблем со ссылками'
);
process.exit(failed === 0 ? 0 : 1);
