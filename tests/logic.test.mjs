/**
 * Проверка чистой логики из index.html без браузера:
 * русская морфология поиска, подсветка, статусы, склонения.
 *
 * Запуск: node tests/logic.test.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

const html = readFileSync(join(root, 'index.html'), 'utf8');

// Вырезаем чистый блок: от escapeHtml до конца snippetAround.
const start = html.indexOf('function escapeHtml');
const end = html.indexOf('/* ---------- список слева');
if (start < 0 || end < 0) throw new Error('не нашёл границы логического блока в index.html');
const block = html.slice(start, end);

const api = new Function(
  block + '\nreturn {escapeHtml, buildPattern, makeRe, highlight, stemRu, statusOf, dateOf, plural};'
)();

let failed = 0;
let passed = 0;
function check(name, cond, extra) {
  if (cond) { passed++; }
  else { failed++; console.log('  FAIL ' + name + (extra ? '  → ' + extra : '')); }
}

function matches(query, text) {
  const re = api.makeRe(api.buildPattern(query), 'i');
  return re ? re.test(text) : false;
}

console.log('— морфология —');
check('убийство → убийств', api.stemRu('убийство') === 'убийств', api.stemRu('убийство'));
check('лицензия → лиценз', api.stemRu('лицензия') === 'лиценз', api.stemRu('лицензия'));
check('закона → закон', api.stemRu('закона') === 'закон', api.stemRu('закона'));
check('12.8 не трогается', api.stemRu('12.8') === '12.8');

console.log('— поиск находит словоформы —');
check('убийство → «за убийства»', matches('убийство', 'наказание за убийства'));
check('убийства → «убийство»', matches('убийства', 'совершил убийство'));
check('лицензия → «лицензии»', matches('лицензия', 'выдача лицензии на бизнес'));
check('статья → «статьи»', matches('статья', 'положения статьи 12.8'));
check('закон → «закона»', matches('закон', 'нарушение закона о полиции'));
check('судья → «судьи»', matches('судья', 'решение судьи Верховного суда'));
check('12.8 → «12.8.1»', matches('12.8', 'ст. 12.8.1 УАК'));
check('два слова рядом', matches('открытое ношение', 'за открытое ношение оружия'));
check('ложное срабатывание исключено', !matches('убийство', 'убитый телефон'));

console.log('— подсветка —');
{
  const out = api.highlight('за убийства и убийство', api.buildPattern('убийство'));
  const marks = (out.match(/<mark>/g) || []).length;
  check('две подсветки', marks === 2, out);
  check('совпадение внутри mark', out.includes('<mark>убийства</mark>'), out);
}
{
  const out = api.highlight('<script>alert(1)</script>', api.buildPattern('script'));
  check('экранирование <script>', !out.includes('<script>'), out);
  check('угловые скобки экранированы', out.startsWith('&lt;') && out.endsWith('&gt;'), out);
  check('текст не потерялся', out.includes('alert(1)'), out);
  check('нет экранированного тега внутри mark', out.includes('<mark>script</mark>'), out);
}

console.log('— статусы и даты —');
check('утратил силу', api.statusOf({title: 'Решение ВС от 29.08.2025 (№289) [УТРАТИЛ СИЛУ]'}) === 'void');
check('на рассмотрении', api.statusOf({title: 'На рассмотрении Обращение в ВС №362'}) === 'pending');
check('обычный', api.statusOf({title: 'Конституция Штата Сан-Андреас'}) === 'active');
check('дата из заголовка', api.dateOf({title: 'Решение ВС от 14.09.2024 (№22)'}) === '14.09.2024');
check('без даты', api.dateOf({title: 'Этический кодекс'}) === '');

console.log('— склонения —');
check('1 документ', api.plural(1, 'документ', 'документа', 'документов') === 'документ');
check('3 документа', api.plural(3, 'документ', 'документа', 'документов') === 'документа');
check('11 документов', api.plural(11, 'документ', 'документа', 'документов') === 'документов');
check('82 документа', api.plural(82, 'документ', 'документа', 'документов') === 'документа');

console.log('— на реальной базе —');
{
  const docs = JSON.parse(readFileSync(join(root, 'docs.json'), 'utf8'));
  const naive = (q) => docs.filter(d => d.text.toLowerCase().includes(q.toLowerCase())).length;
  const smart = (q) => {
    const re = api.makeRe(api.buildPattern(q), 'i');
    return docs.filter(d => re.test(d.title) || re.test(d.text)).length;
  };
  console.log('  документов в базе: ' + docs.length);
  for (const [q, expectMore] of [['убийство', true], ['лицензия', true], ['задержание', true]]) {
    const a = naive(q), b = smart(q);
    console.log('  «' + q + '»: точная подстрока ' + a + ' → морфология ' + b);
    if (expectMore) check('«' + q + '» находит не меньше', b >= a, a + ' vs ' + b);
  }
  const total = docs.reduce((s, d) => s + d.text.length, 0);
  console.log('  символов: ' + total.toLocaleString('ru-RU'));
}

console.log('');
console.log(failed === 0 ? ('OK: ' + passed + ' проверок пройдено') : (failed + ' провалено, ' + passed + ' пройдено'));
process.exit(failed === 0 ? 0 : 1);
