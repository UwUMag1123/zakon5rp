#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка статики «Кодекс Murrieta» из единственного источника данных.

Источник истины: docs.json — массив объектов {id, section, sectionName, title, text}.

Что генерируется:
  codex.json / law.json / appeal.json / other.json  — порезанная база (компактный JSON)
  docs/index.html                                   — список всех документов
  docs/<id>.html                                    — по одной статичной странице на документ
  sitemap.xml                                       — карта сайта с реальными URL
  404.html                                          — страница «не найдено»

Запуск:
  python build.py            # пересобрать всё
  python build.py --check    # проверить, что сгенерированное совпадает с тем, что в репозитории

Код возврата 1 в режиме --check означает «файлы устарели, надо пересобрать».
"""

import html
import json
import os
import re
import sys
from datetime import date

SITE = "https://zakon5rp.pages.dev"
SITE_NAME = "Кодекс Murrieta"

ROOT = os.path.dirname(os.path.abspath(__file__))

# Чтобы «Собрано файлов» не превращалось в кракозябры в консоли Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Порядок разделов в навигации и подписи к ним.
SECTIONS = [
    ("codex", "Кодексы"),
    ("law", "Законы"),
    ("precedent", "Судебные прецеденты и толкования"),
    ("appeal", "Решения Верховного суда по обращениям"),
    ("method", "Методички по отдельным вопросам"),
    ("casebook", "Разбор кейсов и типовых ситуаций"),
    ("course", "Учебный курс (Академия прокуратуры)"),
]
SECTION_LABEL = dict(SECTIONS)
SECTION_ORDER = {s: i for i, (s, _) in enumerate(SECTIONS)}

# Во что складываются чанки. other.json — всё, что не codex/law/appeal.
CHUNKS = [
    ("codex.json", ("codex",)),
    ("law.json", ("law",)),
    ("appeal.json", ("appeal",)),
    ("other.json", ("precedent", "method", "casebook", "course")),
]

# Правила определения статуса документа по заголовку (те же, что в index.html).
RE_VOID = re.compile(r"утратил\s+силу", re.I)
RE_PENDING = re.compile(r"на\s+рассмотрении", re.I)
RE_DATE = re.compile(r"(?:^|\s)от\s+(\d{2})\.(\d{2})\.(\d{4})")

STATUS_LABEL = {
    "active": "",
    "void": "утратил силу",
    "pending": "на рассмотрении",
}


# ----------------------------------------------------------------------------- utils

def esc(s):
    return html.escape(s, quote=True)


def plural_ru(n, one, few, many):
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return one
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return few
    return many


def docs_word(n):
    return plural_ru(n, "документ", "документа", "документов")


def load_docs():
    path = os.path.join(ROOT, "docs.json")
    with open(path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    return docs


def validate(docs):
    errors = []
    seen = set()
    for i, d in enumerate(docs):
        for field in ("id", "section", "title", "text"):
            if not d.get(field):
                errors.append("документ #%d: пустое поле %r" % (i, field))
        if d.get("id") in seen:
            errors.append("дублирующийся id: %r" % d.get("id"))
        seen.add(d.get("id"))
        if d.get("section") not in SECTION_LABEL:
            errors.append("%s: неизвестный section %r" % (d.get("id"), d.get("section")))
        if re.search(r"<script|javascript:", d.get("text", ""), re.I):
            errors.append("%s: в тексте найден подозрительный скрипт" % d.get("id"))
    if errors:
        raise SystemExit("Ошибки в docs.json:\n  " + "\n  ".join(errors))


def status_of(doc):
    title = doc["title"]
    if RE_VOID.search(title):
        return "void"
    if RE_PENDING.search(title):
        return "pending"
    return "active"


def date_of(doc):
    m = RE_DATE.search(doc["title"])
    return "%s.%s.%s" % m.groups() if m else None


def sort_key(doc):
    m = re.match(r"^([a-z]+)-(\d+)$", doc["id"])
    if m:
        return (SECTION_ORDER.get(doc["section"], 99), m.group(1), int(m.group(2)))
    return (SECTION_ORDER.get(doc["section"], 99), doc["id"], 0)


def write(path, content, check, problems):
    full = os.path.join(ROOT, path)
    if check:
        try:
            with open(full, "r", encoding="utf-8", newline="") as f:
                old = f.read().replace("\r\n", "\n")
        except FileNotFoundError:
            problems.append("%s: файла нет" % path)
            return
        if old != content:
            problems.append("%s: устарел" % path)
        return
    if os.path.dirname(full):
        os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# ----------------------------------------------------------------------------- CSS

PAGE_CSS = """
:root{--bg:#f3efe6;--paper:#fffdf8;--ink:#201c14;--ink-dim:#6b6456;--rule:#d8d0bd;
--accent:#8a1f1f;--gold:#9c7a2e;--mark:#f3dca0;--mono-bg:#eae4d4;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#15130f;--paper:#1c1a14;--ink:#ece6d6;
--ink-dim:#a39a84;--rule:#3a3528;--accent:#d08a5c;--gold:#c9a24b;--mark:#4a3c1e;
--mono-bg:#24211a;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"PT Serif",Georgia,
"Times New Roman",serif;line-height:1.75;font-size:16px}
.wrap{max-width:800px;margin:0 auto;padding:26px 18px 90px}
a{color:var(--accent)}
.nav{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
font-family:"PT Sans",Arial,sans-serif;font-size:13px;margin-bottom:22px}
.meta{font-family:"PT Sans",Arial,sans-serif;font-size:11.5px;color:var(--ink-dim);
text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;display:flex;
gap:10px;align-items:center;flex-wrap:wrap}
h1{font-size:clamp(22px,3.4vw,30px);line-height:1.25;margin:0 0 18px;text-wrap:balance}
.badge{font-family:"PT Sans",Arial,sans-serif;font-size:10.5px;font-weight:700;
letter-spacing:.06em;border:1px solid var(--gold);color:var(--gold);border-radius:3px;
padding:2px 6px;text-transform:uppercase}
.badge.void{border-color:var(--accent);color:var(--accent)}
.body{background:var(--paper);border:1px solid var(--rule);border-radius:3px;
padding:clamp(16px,4vw,36px);white-space:pre-wrap;word-wrap:break-word;
font-size:15.5px;line-height:1.75}
.pager{display:flex;justify-content:space-between;gap:12px;margin-top:26px;
font-family:"PT Sans",Arial,sans-serif;font-size:13.5px}
.pager a{text-decoration:none}
.pager .lbl{display:block;font-size:10.5px;text-transform:uppercase;
letter-spacing:.08em;color:var(--ink-dim)}
footer{margin-top:40px;border-top:1px solid var(--rule);padding-top:14px;
font-family:"PT Sans",Arial,sans-serif;font-size:12px;color:var(--ink-dim)}
ul.docs{list-style:none;padding:0;margin:0 0 6px}
ul.docs li{border-bottom:1px solid var(--rule)}
ul.docs a{display:block;padding:7px 2px;text-decoration:none;color:var(--ink);font-size:14.5px}
ul.docs a:hover{color:var(--accent)}
ul.docs .n{color:var(--ink-dim);font-family:"PT Sans",Arial,sans-serif;font-size:12px;
margin-right:8px;display:inline-block;min-width:3.2em}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.1em;color:var(--gold);
font-family:"PT Sans",Arial,sans-serif;margin:30px 0 6px}
.count{font-family:"PT Sans",Arial,sans-serif;font-size:12px;color:var(--ink-dim)}
"""


def page(title, description, body, canonical=None):
    canonical_tag = '<link rel="canonical" href="%s">' % esc(canonical) if canonical else ""
    return (
        "<!doctype html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>%s</title>\n"
        '<meta name="description" content="%s">\n'
        "%s\n"
        "<style>%s</style>\n</head>\n<body>\n<div class=\"wrap\">\n%s\n</div>\n</body>\n</html>\n"
        % (esc(title), esc(description), canonical_tag, PAGE_CSS, body)
    )


def badge(status):
    label = STATUS_LABEL.get(status)
    if not label:
        return ""
    cls = "badge void" if status == "void" else "badge"
    return '<span class="%s">%s</span>' % (cls, esc(label))


# ----------------------------------------------------------------------------- генераторы

def build_doc_page(doc, prev_doc, next_doc):
    st = status_of(doc)
    d = date_of(doc)
    meta_bits = [esc(SECTION_LABEL[doc["section"]])]
    if d:
        meta_bits.append(esc(d))
    if badge(st):
        meta_bits.append(badge(st))

    pager = ['<div class="pager">']
    if prev_doc:
        pager.append(
            '<a href="%s.html">&larr; <span class="lbl">предыдущий</span>%s</a>'
            % (esc(prev_doc["id"]), esc(prev_doc["title"]))
        )
    else:
        pager.append("<span></span>")
    if next_doc:
        pager.append(
            '<a href="%s.html" style="text-align:right"><span class="lbl">следующий</span>%s &rarr;</a>'
            % (esc(next_doc["id"]), esc(next_doc["title"]))
        )
    else:
        pager.append("<span></span>")
    pager.append("</div>")

    body = (
        '<nav class="nav"><a href="../index.html#%s">&larr; %s</a>'
        '<a href="index.html">Все документы &rarr;</a></nav>\n'
        '<div class="meta">%s</div>\n'
        "<h1>%s</h1>\n"
        '<div class="body">%s</div>\n'
        "%s\n"
        '<footer>Статическая копия документа из базы «%s». '
        "Актуальная версия и поиск — <a href=\"../index.html#%s\">на главной странице</a>.</footer>"
        % (
            esc(doc["id"]),
            esc(SITE_NAME),
            " · ".join(meta_bits),
            esc(doc["title"]),
            esc(doc["text"]),
            "\n".join(pager),
            esc(SITE_NAME),
            esc(doc["id"]),
        )
    )
    desc = "%s — %s. Полный текст без сокращений." % (
        doc["title"],
        SECTION_LABEL[doc["section"]],
    )
    return page(
        "%s — %s" % (doc["title"], SITE_NAME),
        desc,
        body,
        canonical="%s/docs/%s.html" % (SITE, doc["id"]),
    )


def build_index_page(docs):
    parts = []
    total = len(docs)
    parts.append(
        '<nav class="nav"><a href="../index.html">&larr; %s</a>'
        '<a href="../index.html">Поиск по базе &rarr;</a></nav>' % esc(SITE_NAME)
    )
    parts.append("<h1>Все документы</h1>")
    parts.append(
        '<p class="count">%d %s в базе. Полные тексты без сокращений, '
        "сгруппированы по разделам.</p>" % (total, docs_word(total))
    )
    for sec, label in SECTIONS:
        items = [d for d in docs if d["section"] == sec]
        if not items:
            continue
        parts.append("<h2>%s <span class=\"count\">(%d)</span></h2>" % (esc(label), len(items)))
        parts.append('<ul class="docs">')
        for d in items:
            st = status_of(d)
            mark = ""
            if st == "void":
                mark = ' <span class="badge void">утратил силу</span>'
            elif st == "pending":
                mark = ' <span class="badge">на рассмотрении</span>'
            parts.append(
                '<li><a href="%s.html"><span class="n">%s</span>%s%s</a></li>'
                % (esc(d["id"]), esc(d["id"].split("-")[-1]), esc(d["title"]), mark)
            )
        parts.append("</ul>")
    parts.append(
        '<footer>Машиночитаемая версия всей базы: '
        '<a href="../docs.json">docs.json</a> (%d %s).</footer>' % (total, docs_word(total))
    )
    return page(
        "Все документы — %s" % SITE_NAME,
        "Список всех %d %s законодательной базы сервера Murrieta: кодексы, законы, "
        "прецеденты и решения Верховного суда." % (total, docs_word(total)),
        "\n".join(parts),
        canonical="%s/docs/index.html" % SITE,
    )


def build_sitemap(docs, today):
    urls = [("%s/" % SITE, "1.0"), ("%s/docs/index.html" % SITE, "0.8")]
    for d in docs:
        urls.append(("%s/docs/%s.html" % (SITE, d["id"]), "0.7"))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, prio in urls:
        lines.append(
            "  <url><loc>%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>"
            % (esc(loc), today, prio)
        )
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def build_404():
    body = (
        '<nav class="nav"><a href="/">%s</a></nav>'
        "<h1>Страница не найдена</h1>"
        '<p>Такого документа в базе нет. Откройте <a href="/">главную страницу</a> '
        'или <a href="/docs/index.html">список всех документов</a>.</p>'
        % esc(SITE_NAME)
    )
    return page("Страница не найдена — %s" % SITE_NAME, "Страница не найдена.", body)


# ----------------------------------------------------------------------------- сборка

def generate():
    docs = load_docs()
    validate(docs)
    docs_sorted = sorted(docs, key=sort_key)
    today = date.today().isoformat()
    out = {}

    # чанки
    for fname, secs in CHUNKS:
        chunk = [d for d in docs_sorted if d["section"] in secs]
        out[fname] = json.dumps(chunk, ensure_ascii=False, separators=(",", ":"))

    # постраничные файлы
    per_section = {}
    for d in docs_sorted:
        per_section.setdefault(d["section"], []).append(d)
    for sec, items in per_section.items():
        for i, d in enumerate(items):
            prev_doc = items[i - 1] if i > 0 else None
            next_doc = items[i + 1] if i + 1 < len(items) else None
            out["docs/%s.html" % d["id"]] = build_doc_page(d, prev_doc, next_doc)

    out["docs/index.html"] = build_index_page(docs_sorted)
    out["sitemap.xml"] = build_sitemap(docs_sorted, today)
    out["404.html"] = build_404()
    out["robots.txt"] = "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE
    return out


def main():
    check = "--check" in sys.argv
    files = generate()
    problems = []
    for path, content in sorted(files.items()):
        write(path, content, check, problems)

    if check:
        if problems:
            print("Сгенерированные файлы устарели (%d):" % len(problems))
            for p in problems:
                print("  - " + p)
            print("\nЗапустите: python build.py")
            return 1
        print("OK: все сгенерированные файлы актуальны (%d)." % len(files))
        return 0

    print("Собрано файлов: %d" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
