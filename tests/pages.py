#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка сгенерированных страниц: текст внутри страницы должен совпадать
с docs.json символ в символ, теги — не протекать.

Запуск: python tests/pages.py
"""

import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RE_BODY = re.compile(r'<div class="body">(.*?)</div>\n', re.S)
RE_TITLE = re.compile(r"<h1>(.*?)</h1>", re.S)

failed = 0
checked = 0


def fail(msg):
    global failed
    failed += 1
    print("  FAIL " + msg)


with open(os.path.join(ROOT, "docs.json"), encoding="utf-8") as f:
    docs = json.load(f)

for d in docs:
    path = os.path.join(ROOT, "docs", d["id"] + ".html")
    if not os.path.exists(path):
        fail("%s: нет файла страницы" % d["id"])
        continue
    with open(path, encoding="utf-8") as f:
        page = f.read()
    checked += 1

    m = RE_BODY.search(page)
    if not m:
        fail("%s: не найден блок текста" % d["id"])
        continue
    text = html.unescape(m.group(1))
    if text != d["text"]:
        fail("%s: текст на странице не совпадает с docs.json" % d["id"])
        # подсказка, где расходится
        for i, (a, b) in enumerate(zip(text, d["text"])):
            if a != b:
                print("        первое расхождение на позиции %d: %r vs %r" % (i, text[i:i + 40], d["text"][i:i + 40]))
                break
        else:
            print("        длина страницы %d, в данных %d" % (len(text), len(d["text"])))

    mt = RE_TITLE.search(page)
    if not mt or mt.group(1) != html.escape(d["title"]):
        fail("%s: заголовок в <h1> не совпадает" % d["id"])

    if re.search(r"утратил\s+силу", d["title"], re.I) and "утратил силу" not in page:
        fail("%s: нет плашки «утратил силу»" % d["id"])

# оглавление: ссылка на каждый документ
idx_path = os.path.join(ROOT, "docs", "index.html")
with open(idx_path, encoding="utf-8") as f:
    idx = f.read()
for d in docs:
    if ('href="%s.html"' % d["id"]) not in idx:
        fail("docs/index.html: нет ссылки на %s" % d["id"])

print("")
if failed:
    print("%d проблем, проверено %d страниц" % (failed, checked))
    sys.exit(1)
print("OK: %d страниц, текст совпадает с docs.json" % checked)
