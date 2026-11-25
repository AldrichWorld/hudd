"""Translations: all 13 languages have exactly the same keys and placeholders as English, every key the pages
use exists, and no text mentions another product name."""
import json
import re
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "web" / "static"
js = (STATIC / "js" / "i18n.js").read_text(encoding="utf-8")
# the script goes in on stdin (i18n.js is larger than one command-line argument may be)
out = subprocess.run(["node"], input="global.window={};global.document={querySelectorAll:()=>[],documentElement:{dataset:{}}};"
                      "global.localStorage={getItem:()=>null,setItem:()=>{}};global.location={search:''};"
                      + js + ";const r={};for(const l of I18N.LANGS)r[l.code]=I18N.dict(l.code);console.log(JSON.stringify(r))",
                     capture_output=True, text=True, check=True).stdout
D = json.loads(out)
assert len(D) == 13, list(D)
ph = lambda s: sorted(set(re.findall(r"\{(\w+)\}", s)))
en = D["en"]
for lang, d in D.items():
    assert set(d) == set(en), (lang, set(en) ^ set(d))
    for k in en:
        assert ph(d[k]) == ph(en[k]), (lang, k, d[k])
        assert "Huddle" not in d[k], (lang, k)
pages = "".join((STATIC / f).read_text(encoding="utf-8") for f in ("index.html", "room.html", "js/room.js", "js/home.js", "js/common.js"))
used = set(re.findall(r'data-i18n(?:-html|-ph|-title)?="([^"]+)"', pages)) | set(re.findall(r"\bt\('([\w.]+)'", pages))
assert used <= set(en), used - set(en)
print(f"1 13 languages × {len(en)} strings: same keys and placeholders everywhere; every key the pages use exists")
print("I18N OK")
