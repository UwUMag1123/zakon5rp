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
:root{--bg:#08090b;--surface:#0e1014;--surface-2:#15181e;--line:rgba(255,255,255,.08);
--line-2:rgba(255,255,255,.18);--ink:#f2efe8;--ink-2:#a6acb5;--ink-3:#6f767f;
--accent:#e2452b;--accent-2:#ff6a4d;--accent-soft:rgba(226,69,43,.14);color-scheme:dark}
@media (prefers-color-scheme:light){:root{--bg:#f2efe7;--surface:#fffdf8;--surface-2:#efeae0;
--line:rgba(18,15,12,.12);--line-2:rgba(18,15,12,.26);--ink:#13110e;--ink-2:#5e574c;
--ink-3:#8b8274;--accent:#b8301a;--accent-2:#d14428;--accent-soft:rgba(184,48,26,.10);
color-scheme:light}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Inter Tight",system-ui,
-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased;font-size:16px}
.wrap{max-width:820px;margin:0 auto;padding:34px 20px 110px}
a{color:var(--accent);text-decoration:none}
a:hover{color:var(--accent-2)}
.nav{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
font-family:"JetBrains Mono",monospace;font-size:10px;letter-spacing:.14em;
text-transform:uppercase;color:var(--ink-3);margin-bottom:26px;
padding-bottom:14px;border-bottom:1px solid var(--line)}
.meta{font-family:"JetBrains Mono",monospace;font-size:9.5px;color:var(--ink-3);
letter-spacing:.14em;text-transform:uppercase;margin-bottom:14px;display:flex;
gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:clamp(26px,4vw,44px);line-height:1.04;letter-spacing:-.03em;font-weight:600;
margin:0 0 22px;text-wrap:balance}
.badge{font-family:"JetBrains Mono",monospace;font-size:8.5px;font-weight:500;
letter-spacing:.12em;border:1px solid var(--accent);color:var(--accent);border-radius:3px;
padding:3px 7px;text-transform:uppercase}
.badge.void{background:var(--accent);color:#fff}
.body{background:var(--surface);border:1px solid var(--line);border-radius:12px;
padding:clamp(18px,3.4vw,40px);white-space:pre-wrap;word-wrap:break-word;
font-family:"PT Serif",Georgia,serif;font-size:16.5px;line-height:1.78}
.pager{display:flex;justify-content:space-between;gap:12px;margin-top:34px;
font-family:"Inter Tight",sans-serif;font-size:13px;color:var(--ink-2)}
.pager .lbl{display:block;font-family:"JetBrains Mono",monospace;font-size:9px;
text-transform:uppercase;letter-spacing:.14em;color:var(--ink-3);margin-bottom:4px}
footer{margin-top:46px;border-top:1px solid var(--line);padding-top:16px;
font-family:"JetBrains Mono",monospace;font-size:10px;letter-spacing:.06em;color:var(--ink-3)}
ul.docs{list-style:none;padding:0;margin:0 0 10px}
ul.docs li{border-bottom:1px solid var(--line)}
ul.docs a{display:block;padding:10px 2px;text-decoration:none;color:var(--ink);font-size:14px}
ul.docs a:hover{color:var(--accent)}
ul.docs .n{color:var(--ink-3);font-family:"JetBrains Mono",monospace;font-size:11px;
margin-right:10px;display:inline-block;min-width:3.4em}
ul.docs .path{font-family:"JetBrains Mono",monospace;font-size:9.5px;color:var(--ink-3);
margin-left:8px;white-space:nowrap}
h2{font-family:"JetBrains Mono",monospace;font-size:9.5px;text-transform:uppercase;
letter-spacing:.18em;color:var(--ink-3);margin:36px 0 8px;display:flex;align-items:center;gap:8px}
h2::before{content:"";width:5px;height:5px;background:var(--accent)}
.count{font-family:"JetBrains Mono",monospace;font-size:10.5px;color:var(--ink-3);
letter-spacing:.04em}
"""

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Inter+Tight:wght@400;500;600;700&family=PT+Serif:wght@400;700&'
    'family=JetBrains+Mono:wght@400;500&display=swap">'
)


def page(title, description, body, canonical=None):
    canonical_tag = '<link rel="canonical" href="%s">' % esc(canonical) if canonical else ""
    return (
        "<!doctype html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>%s</title>\n"
        '<meta name="description" content="%s">\n'
        "%s\n%s\n"
        "<style>%s</style>\n</head>\n<body>\n<div class=\"wrap\">\n%s\n</div>\n</body>\n</html>\n"
        % (esc(title), esc(description), canonical_tag, FONT_LINK, PAGE_CSS, body)
    )


def badge(status):
    label = STATUS_LABEL.get(status)
    if not label:
        return ""
    cls = "badge void" if status == "void" else "badge"
    return '<span class="%s">%s</span>' % (cls, esc(label))


# ----------------------------------------------------------------------------- генераторы

def build_doc_page(doc, prev_doc, next_doc, book_index=None):
    book_link = ""
    if book_index:
        book_link = " Оглавление документа: <a href=\"%s\">по частям</a>." % esc(book_index)
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
        "Актуальная версия и поиск — <a href=\"../index.html#%s\">на главной странице</a>.%s</footer>"
        % (
            esc(doc["id"]),
            esc(SITE_NAME),
            " · ".join(meta_bits),
            esc(doc["title"]),
            esc(doc["text"]),
            "\n".join(pager),
            esc(SITE_NAME),
            esc(doc["id"]),
            book_link,
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


def build_sitemap(docs, today, extra_paths=()):
    urls = [("%s/" % SITE, "1.0"), ("%s/docs/index.html" % SITE, "0.8")]
    for d in docs:
        urls.append(("%s/docs/%s.html" % (SITE, d["id"]), "0.7"))
    for path in extra_paths:
        urls.append(("%s/%s" % (SITE, path), "0.6"))
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


# ----------------------------------------------------------------------------- статьи кодексов и навигация

# УАК нумерует статьи как 12.8 / 12.8.1, иногда с маркером юрисдикции впереди.
RE_ARTICLE_DOTTED = re.compile(r"^(?:[\U0001F7E5\U0001F7E9\U0001F7E8]\s*)?(\d+\.\d+(?:\.\d+)*)\.?\s*\S")
# остальные кодексы — «Статья 12. Текст» (в Дорожном точка после номера ставится не всегда)
RE_ARTICLE_STAT = re.compile(r"^\s*Статья\s+(\d+(?:\.\d+)*)\.?(?:\s+\S|\s*$)", re.M)
RE_CHAPTER = re.compile(r"^\s*(?:Глава|Раздел)\s+([IVXLCDM]+|\d+(?:\.\d+)?)[\.\s]*(.*?)\s*$")
RE_ART_IN_TEXT = re.compile(r"(?<![\d.])(\d+\.\d+(?:\.\d+)*)(?![\d.])")
# «🟥12.8 [У]…» в начале статьи: номер уже стоит в заголовке страницы
RE_LEAD_NUMBER = re.compile(r"^[\U0001F7E5\U0001F7E9\U0001F7E8]?\s*\d+\.\d+(?:\.\d+)*\.?\s*")
RE_NUM = re.compile(r"№\s*(\d+)")

# id кодекса -> (папка, короткое имя, режим разбивки)
#   dotted  — статьи вида 12.8 (нумерация уникальна по всему кодексу)
#   article — «Статья N.» с уникальной нумерацией
#   chapter — нумерация статей своя в каждой главе, поэтому режем по главам
CODEBOOKS = [
    ("codex-2", "uak", "УАК", "dotted"),
    ("codex-1", "konst", "Конституции", "article"),
    ("codex-3", "pk", "ПК", "chapter"),
    ("codex-4", "sud", "СК", "chapter"),
    ("codex-5", "trud", "ТК", "article"),
    ("codex-6", "dor", "ДК", "chapter"),
]

# большие подборки прецедентов режем по размеру: структура внутри неоднородна
COLLECTIONS = ["precedent-1", "precedent-2", "precedent-3"]
CHUNK_LIMIT = 12000


def parse_document(text, mode):
    """Режет кодекс на части: статьи или главы."""
    lines = text.split("\n")

    if mode == "chapter":
        marks = []
        for i, ln in enumerate(lines):
            m = RE_CHAPTER.match(ln)
            if m:
                marks.append((i, m.group(1), (m.group(2) or "").strip()))
        parts = []
        for k, (start, key, title) in enumerate(marks):
            end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
            body = "\n".join(lines[start:end]).strip()
            parts.append({
                "key": key,
                "title": title,
                "text": body,
                "articles": RE_ARTICLE_STAT.findall(body),
            })
    else:
        re_art = RE_ARTICLE_DOTTED if mode == "dotted" else RE_ARTICLE_STAT
        chapter = ""
        marks = []
        for i, ln in enumerate(lines):
            m_ch = RE_CHAPTER.match(ln)
            if m_ch:
                chapter = "Глава %s%s" % (m_ch.group(1), (". " + m_ch.group(2)) if m_ch.group(2) else "")
                continue
            m = re_art.match(ln)
            if m:
                marks.append((i, m.group(1), chapter))

        parts = []
        for k, (start, num, chap) in enumerate(marks):
            end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
            parts.append({
                "key": num,
                "title": chap,
                "text": "\n".join(lines[start:end]).strip(),
                "articles": [num],
            })

    # вводная часть до первой главы или статьи не должна пропадать
    if marks and marks[0][0] > 0:
        head = "\n".join(lines[:marks[0][0]]).strip()
        if len(head) > 40:
            parts[0]["text"] = head + "\n\n" + parts[0]["text"]
            if mode == "chapter":
                parts[0]["articles"] = RE_ARTICLE_STAT.findall(parts[0]["text"])

    return parts


def part_heading(part, short, mode):
    if mode == "chapter":
        return "Глава %s. %s" % (part["key"], part["title"]) if part["title"] else "Глава %s" % part["key"]
    return "Ст. %s %s" % (part["key"], short)


def part_title_line(part, mode):
    """Первая содержательная строка — для оглавления и описания."""
    line = part["text"].split("\n")[0]
    if mode == "chapter":
        line = RE_CHAPTER.sub("", line).strip()
        line = line.lstrip(".").strip()
    else:
        re_art = RE_ARTICLE_DOTTED if mode == "dotted" else RE_ARTICLE_STAT
        line = re_art.sub("", line).strip()
    return line.lstrip("*").strip()[:130]


def article_refs(parts, docs, mode):
    """Для каждой статьи — документы базы, где она упоминается (только УАК)."""
    if mode != "dotted":
        return {}
    where = {}
    for d in docs:
        if d["id"].startswith("codex-"):
            continue
        for num in set(RE_ART_IN_TEXT.findall(d["text"])):
            where.setdefault(num, []).append(d)
    weight = {"appeal": 0, "precedent": 1, "method": 2, "casebook": 3, "course": 4}
    refs = {}
    for p in parts:
        items = sorted(where.get(p["key"], []), key=lambda d: weight.get(d["section"], 9))
        refs[p["key"]] = items[:6]
    return refs


def build_code_pages(doc, folder, short, mode, docs):
    parts = parse_document(doc["text"], mode)
    refs = article_refs(parts, docs, mode)
    out = {}
    # папка может быть вложенной (law/20), поэтому подъём до docs/ считается по глубине
    up = "../" * (folder.count("/") + 1)

    for p in parts:
        heading = part_heading(p, short, mode)
        title_line = part_title_line(p, mode)
        meta = [esc(short), esc(p["title"])] if p["title"] and mode != "chapter" else [esc(short)]

        extra = ""
        if mode == "chapter" and p["articles"]:
            extra += (
                '<p class="count">Статьи в главе: %s</p>\n' % esc(", ".join(p["articles"]))
            )
        items = refs.get(p["key"]) or []
        if items:
            links = "".join(
                '<li><a href="%s%s.html">%s</a> <span class="path">docs/%s.html</span></li>'
                % (up, esc(d["id"]), esc(d["title"]), esc(d["id"])) for d in items
            )
            extra += '<h2>Где упоминается</h2>\n<ul class="docs">%s</ul>\n' % links

        body_text = p["text"]
        if mode == "dotted":
            body_text = RE_LEAD_NUMBER.sub("", body_text, count=1)

        body = (
            '<nav class="nav"><a href="%s%s.html">&larr; %s</a>'
            '<a href="index.html">Оглавление &rarr;</a></nav>\n'
            '<div class="meta">%s</div>\n'
            "<h1>%s</h1>\n"
            '<div class="body">%s</div>\n'
            "%s"
            '<footer>Полный документ — <a href="%s%s.html">docs/%s.html</a>. База «%s».</footer>'
            % (
                up, esc(doc["id"]), esc(doc["title"]), " · ".join(meta), esc(heading),
                esc(body_text), extra, up, esc(doc["id"]), esc(doc["id"]), esc(SITE_NAME),
            )
        )
        out["docs/%s/%s.html" % (folder, p["key"])] = page(
            "%s — %s" % (heading, SITE_NAME),
            "%s. %s: полный текст." % (title_line[:110], heading),
            body,
            canonical="%s/docs/%s/%s.html" % (SITE, folder, p["key"]),
        )

    # оглавление
    total_articles = sum(len(p["articles"]) for p in parts)
    parts_html = [
        '<nav class="nav"><a href="%s%s.html">&larr; %s</a>'
        '<a href="%sindex.html">Все документы &rarr;</a></nav>'
        % (up, esc(doc["id"]), esc(SITE_NAME), up),
        "<h1>%s — оглавление</h1>" % esc(doc["title"]),
        '<p class="count">%d %s, %d %s. Адрес страницы: docs/%s/&lt;номер&gt;.html</p>'
        % (
            len(parts),
            plural_ru(len(parts), "глава", "главы", "глав") if mode == "chapter"
            else plural_ru(len(parts), "часть", "части", "частей"),
            total_articles,
            plural_ru(total_articles, "статья", "статьи", "статей"),
            folder,
        ),
    ]
    if mode == "chapter":
        parts_html.append('<ul class="docs">')
        for p in parts:
            parts_html.append(
                '<li><a href="%s.html"><span class="n">%s</span>%s <span class="count">(%s)</span></a></li>'
                % (esc(p["key"]), esc(p["key"]), esc(p["title"] or "без названия"),
                   esc(", ".join(p["articles"][:8]) + ("…" if len(p["articles"]) > 8 else "")) or "—")
            )
        parts_html.append("</ul>")
    else:
        chapter = None
        for p in parts:
            if p["title"] != chapter:
                chapter = p["title"]
                parts_html.append("<h2>%s</h2>" % esc(chapter or "Без главы"))
                parts_html.append('<ul class="docs">')
            parts_html.append(
                '<li><a href="%s.html"><span class="n">%s</span>%s</a></li>'
                % (esc(p["key"]), esc(p["key"]), esc(part_title_line(p, mode)[:110]))
            )
        parts_html.append("</ul>")
    out["docs/%s/index.html" % folder] = page(
        "%s — оглавление — %s" % (doc["title"], SITE_NAME),
        "Оглавление: %d статей %s." % (total_articles, doc["title"]),
        "\n".join(parts_html),
        canonical="%s/docs/%s/index.html" % (SITE, folder),
    )
    return out


def split_chunks(text, limit=CHUNK_LIMIT):
    """Режет длинный текст на части по границам строк."""
    lines = text.split("\n")
    chunks, cur, size = [], [], 0
    for ln in lines:
        if cur and size + len(ln) + 1 > limit:
            chunks.append("\n".join(cur).strip())
            cur, size = [], 0
        cur.append(ln)
        size += len(ln) + 1
    if cur:
        chunks.append("\n".join(cur).strip())
    return [c for c in chunks if c]


def chunk_numbers(chunk, limit=12):
    nums = []
    for n in RE_NUM.findall(chunk):
        if n not in nums:
            nums.append(n)
        if len(nums) >= limit:
            break
    return nums


def build_collection_pages(doc, folder):
    """Подборки прецедентов: режем по размеру, потому что структура внутри неоднородна."""
    chunks = split_chunks(doc["text"])
    total = len(chunks)
    up = "../" * (folder.count("/") + 1)
    out = {}

    for i, chunk in enumerate(chunks, 1):
        nums = chunk_numbers(chunk)
        extra = ""
        if nums:
            extra = '<p class="count">Номера в этой части: %s</p>\n' % esc(
                ", ".join("№" + n for n in nums)
            )
        pager = ['<div class="pager">']
        pager.append(
            '<a href="%d.html"><span class="lbl">предыдущая</span>часть %d</a>' % (i - 1, i - 1)
            if i > 1 else "<span></span>"
        )
        pager.append(
            '<a href="%d.html" style="text-align:right"><span class="lbl">следующая</span>часть %d</a>'
            % (i + 1, i + 1)
            if i < total else "<span></span>"
        )
        pager.append("</div>")

        body = (
            '<nav class="nav"><a href="%s%s.html">&larr; %s</a>'
            '<a href="index.html">Оглавление &rarr;</a></nav>\n'
            '<div class="meta">%s · часть %d из %d</div>\n'
            "<h1>%s — часть %d</h1>\n"
            "%s"
            '<div class="body">%s</div>\n'
            "%s"
            '<footer>Целиком — <a href="%s%s.html">docs/%s.html</a>. База «%s».</footer>'
            % (
                up, esc(doc["id"]), esc(SITE_NAME), esc(SECTION_LABEL[doc["section"]]), i, total,
                esc(doc["title"]), i, extra, esc(chunk), "\n".join(pager),
                up, esc(doc["id"]), esc(doc["id"]), esc(SITE_NAME),
            )
        )
        out["docs/%s/%d.html" % (folder, i)] = page(
            "%s — часть %d — %s" % (doc["title"], i, SITE_NAME),
            "%s: часть %d из %d." % (doc["title"], i, total),
            body,
            canonical="%s/docs/%s/%d.html" % (SITE, folder, i),
        )

    items = []
    for i, chunk in enumerate(chunks, 1):
        nums = chunk_numbers(chunk, 6)
        label = ", ".join("№" + n for n in nums) or "без номеров"
        items.append(
            '<li><a href="%d.html"><span class="n">%d</span>часть %d <span class="count">· %s</span></a></li>'
            % (i, i, i, esc(label))
        )
    parts_html = [
        '<nav class="nav"><a href="%s%s.html">&larr; %s</a>'
        '<a href="%sindex.html">Все документы &rarr;</a></nav>'
        % (up, esc(doc["id"]), esc(SITE_NAME), up),
        "<h1>%s</h1>" % esc(doc["title"]),
        '<p class="count">%d %s по ~%d КБ — документ большой и при чтении целиком обрезается.</p>'
        % (total, plural_ru(total, "часть", "части", "частей"), CHUNK_LIMIT // 1000),
        '<ul class="docs">' + "".join(items) + "</ul>",
    ]
    out["docs/%s/index.html" % folder] = page(
        "%s — по частям — %s" % (doc["title"], SITE_NAME),
        "%s: оглавление по частям." % doc["title"],
        "\n".join(parts_html),
        canonical="%s/docs/%s/index.html" % (SITE, folder),
    )
    return out


def build_appeal_nav(docs):
    """Индекс решений и толкований по номерам: №541 -> документ."""
    rows = []
    for d in docs:
        if d["section"] not in ("appeal", "precedent"):
            continue
        m = re.search(r"№\s*(\d+)", d["title"])
        if not m:
            continue
        rows.append((int(m.group(1)), d))
    rows.sort(key=lambda r: r[0])

    body = [
        '<nav class="nav"><a href="../index.html">&larr; %s</a></nav>' % esc(SITE_NAME),
        "<h1>Решения и толкования по номерам</h1>",
        '<p class="count">%d документов. Если в вопросе есть номер (№541, толкование №468) — '
        "открывай документ отсюда.</p>" % len(rows),
        '<ul class="docs">',
    ]
    for num, d in rows:
        mark = ""
        if RE_VOID.search(d["title"]):
            mark = ' <span class="badge void">утратил силу</span>'
        body.append(
            '<li><a href="%s.html"><span class="n">№%d</span>%s%s</a></li>'
            % (esc(d["id"]), num, esc(d["title"]), mark)
        )
    body.append("</ul>")
    return page(
        "Решения и толкования по номерам — %s" % SITE_NAME,
        "Индекс судебных решений и толкований Верховного суда Murrieta по номерам.",
        "\n".join(body),
        canonical="%s/docs/appeal-nav.html" % SITE,
    )


def build_map():
    """Короткая карта базы: один запрос — и понятно, куда идти."""
    text = "\n".join([
        "КОДЕКС MURRIETA — КАРТА БАЗЫ",
        "",
        "94 документа. Все пути относительные от корня базы.",
        "Ссылки внутри страниц тоже относительные: ../appeal-33.html со страницы docs/uak/12.8.html",
        "означает docs/appeal-33.html.",
        "",
        "С ЧЕГО НАЧИНАТЬ",
        "  docs/index.txt            все документы списком: id | раздел | название (18 КБ)",
        "  docs/method-nav.html      методички по темам",
        "  docs/precedent-nav.html   таблица «статья → толкование/прецедент»",
        "  docs/appeal-nav.html      решения и толкования по номерам (№541 → документ)",
        "  docs/casebook-1.html      разборы типовых казусов",
        "",
        "СТАТЬИ И ГЛАВЫ",
        "  docs/uak/<номер>.html                УАК, например docs/uak/12.8.html",
        "  docs/konst/<номер>.html              Конституция",
        "  docs/trud/<номер>.html               Трудовой кодекс",
        "  docs/pk/<глава>.html                 Процессуальный кодекс, например docs/pk/IX.html",
        "  docs/sud/<глава>.html                Судебный кодекс",
        "  docs/dor/<глава>.html                Дорожный кодекс",
        "  docs/law/<номер>/index.html          закон по главам, например docs/law/20/index.html",
        "  docs/prec/precedent-N/index.html     подборка прецедентов по частям",
        "",
        "ЧЕГО НЕ ДЕЛАТЬ",
        "  index.html   — оболочка приложения: без выполнения JS документов в ней нет",
        "  docs.json    — 2,9 МБ, при чтении обрезается; для одной статьи не нужен",
        "  поиск в интернете — выдаёт форумы и соседние серверы, а не эту базу",
    ])
    return text + "\n"


def build_text_index(docs):
    """Плоский текстовый индекс для моделей: id, раздел, название, размер."""
    lines = [
        "КОДЕКС MURRIETA — ИНДЕКС БАЗЫ",
        "Всего документов: %d." % len(docs),
        "",
        "Карта адресов (2 КБ): docs/map.txt",
        "Статьи УАК по номеру: docs/uak/<номер>.html   (например docs/uak/12.8.html)",
        "Оглавление статей УАК: docs/uak/index.html",
        "Статьи других кодексов: docs/pk/<глава>.html, docs/konst/<номер>.html, docs/sud/<глава>.html, docs/trud/<номер>.html, docs/dor/<глава>.html",
        "Законы по главам: docs/law/<номер закона>/index.html   (например docs/law/20/index.html — закон о прокуратуре)",
        "Подборки прецедентов по частям: docs/prec/<id>/index.html   (например docs/prec/precedent-1/index.html)",
        "Решения и толкования по номерам: docs/appeal-nav.html",
        "Методички по темам: docs/method-nav.html",
        "Полный список документов: docs/index.html",
        "",
        "id | раздел | название | знаков | статус",
        "-" * 90,
    ]
    for sec, label in SECTIONS:
        for d in docs:
            if d["section"] != sec:
                continue
            st = status_of(d)
            lines.append(
                "%s | %s | %s | %d | %s"
                % (d["id"], label, d["title"], len(d["text"]), STATUS_LABEL.get(st) or "действует")
            )
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- сборка

def plan_books(docs_sorted):
    """Что режем на части: кодексы и законы.

    Для закона берём главы, если они есть (нумерация статей в законах часто
    начинается заново в каждой главе), иначе — статьи, если номера уникальны.
    """
    plan = []
    for codex_id, folder, short, mode in CODEBOOKS:
        src = next((d for d in docs_sorted if d["id"] == codex_id), None)
        if src:
            plan.append((src, folder, short, mode))

    for d in docs_sorted:
        if d["section"] != "law":
            continue
        num = d["id"].split("-")[-1]
        folder = "law/%s" % num
        short = "Закон №%s" % num
        chapters = parse_document(d["text"], "chapter")
        if len(chapters) >= 2:
            plan.append((d, folder, short, "chapter"))
            continue
        arts = parse_document(d["text"], "article")
        if len(arts) >= 3 and len({a["key"] for a in arts}) == len(arts):
            plan.append((d, folder, short, "article"))
    return plan


def generate():
    docs = load_docs()
    validate(docs)
    docs_sorted = sorted(docs, key=sort_key)
    today = date.today().isoformat()
    out = {}

    plan = plan_books(docs_sorted)
    # относительные пути считаются от docs/, потому что страница документа лежит там
    book_index = {doc["id"]: "%s/index.html" % folder for doc, folder, _short, _mode in plan}
    for d in docs_sorted:
        if d["id"] in COLLECTIONS:
            book_index[d["id"]] = "prec/%s/index.html" % d["id"]

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
            out["docs/%s.html" % d["id"]] = build_doc_page(
                d, prev_doc, next_doc, book_index.get(d["id"])
            )

    out["docs/index.html"] = build_index_page(docs_sorted)

    # страницы статей и глав
    book_paths = []
    for src, folder, short, mode in plan:
        for path, content in build_code_pages(src, folder, short, mode, docs_sorted).items():
            out[path] = content
            if path.endswith(".html"):
                book_paths.append(path)

    out["docs/appeal-nav.html"] = build_appeal_nav(docs_sorted)
    book_paths.append("docs/appeal-nav.html")

    # подборки прецедентов — по частям
    for d in docs_sorted:
        if d["id"] not in COLLECTIONS:
            continue
        folder = "prec/%s" % d["id"]
        for path, content in build_collection_pages(d, folder).items():
            out[path] = content
            if path.endswith(".html"):
                book_paths.append(path)

    out["docs/index.txt"] = build_text_index(docs_sorted)
    out["docs/map.txt"] = build_map()

    out["sitemap.xml"] = build_sitemap(docs_sorted, today, book_paths)
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
