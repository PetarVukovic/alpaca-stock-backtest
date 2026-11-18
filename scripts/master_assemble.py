#!/usr/bin/env python3
"""Assemble the master notebook (self-contained HTML) from the three HTML fragments.

Inputs  (reports/research/MASTER_20261014/):
    part1.html, part2.html, part3.html   HTML fragments (no html/head/body/style/script tags)
    charts/*.png                         referenced via <img data-chart="NAME.png">
Output:
    master.html                          one self-contained file (charts as data URIs)
    build_report.json                    counts, missing charts, structural check results

Read-only with respect to everything else: no network, no orders, no data changes.
Run:  /usr/bin/python3 scripts/master_assemble.py        (any python3 with Pillow is best;
      without Pillow the original PNG bytes are embedded unchanged)
Exit code 1 if a structural check fails; missing charts are listed loudly but do not
abort (the figure is removed instead, so no broken image is left behind).
"""
from __future__ import annotations

import base64
import collections
import glob
import html
import io
import json
import os
import re
import sys
from html.parser import HTMLParser

try:  # optional
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIR = os.path.join(ROOT, "reports", "research", "MASTER_20261014")
CHARTS = os.path.join(DIR, "charts")
PINE_DIR = os.path.join(ROOT, "scripts", "tradingview")
OUT = os.path.join(DIR, "master.html")
REPORT = os.path.join(DIR, "build_report.json")
MAX_WIDTH = 1400
JPEG_QUALITY = 82
MAX_BYTES = 14 * 1024 * 1024

PARTS = [
    ("part1.html", "dio-1", "Dio 1", "Škola i rječnik"),
    ("part2.html", "dio-2", "Dio 2", "Strategije jedna po jedna"),
    ("part3.html", "dio-3", "Dio 3", "Stanje, karta i plan"),
]
FORBIDDEN_IN_FRAGMENT = ("html", "head", "body", "style", "script", "link", "meta", "iframe", "form")


# ----------------------------------------------------------------------------- images
def encode_chart(path: str) -> tuple[str, int, int, int]:
    """Return (data_uri, width, height, byte_size). Optimised PNG, JPEG only if PNG is huge."""
    raw = open(path, "rb").read()
    if Image is None:
        return "data:image/png;base64," + base64.b64encode(raw).decode(), 0, 0, len(raw)
    im = Image.open(io.BytesIO(raw))
    im.load()
    if im.width > MAX_WIDTH:
        h = round(im.height * MAX_WIDTH / im.width)
        im = im.resize((MAX_WIDTH, h), Image.LANCZOS)
    w, h = im.size
    buf = io.BytesIO()
    # palette PNGs stay palette (3x smaller than RGB); other modes are normalised to RGB(A)
    keep = im if im.mode in ("P", "L", "RGB", "RGBA") else im.convert("RGBA")
    keep.save(buf, "PNG", optimize=True)
    png = buf.getvalue()
    mime, data = "image/png", png
    if len(png) > 700_000:  # charts with text stay PNG; only photo-like heavy ones go JPEG
        jb = io.BytesIO()
        im.convert("RGB").save(jb, "JPEG", quality=JPEG_QUALITY, optimize=True)
        if len(jb.getvalue()) < len(png):
            mime, data = "image/jpeg", jb.getvalue()
    return f"data:{mime};base64," + base64.b64encode(data).decode(), w, h, len(data)


FIG_RE = re.compile(r"<figure\b[^>]*class=\"fig\"[^>]*>.*?</figure>", re.S)
IMG_RE = re.compile(r"<img\b[^>]*data-chart=\"([^\"]+)\"[^>]*>", re.S)


def embed_charts(fragment: str, cache: dict, missing: list, used: set) -> str:
    def fig_sub(m: re.Match) -> str:
        fig = m.group(0)
        im = IMG_RE.search(fig)
        if not im:
            return fig
        name = im.group(1)
        used.add(name)
        path = os.path.join(CHARTS, name)
        if not os.path.isfile(path):
            missing.append(name)
            print(f"!! MISSING CHART: {name} (figure removed)", file=sys.stderr)
            return ""
        if name not in cache:
            cache[name] = encode_chart(path)
        uri, w, h, _ = cache[name]
        tag = im.group(0)
        alt = re.search(r'alt="([^"]*)"', tag)
        new = f'<img src="{uri}" alt="{alt.group(1) if alt else ""}" loading="lazy" decoding="async"'
        if w and h:
            new += f' width="{w}" height="{h}"'
        new += ">"
        return fig.replace(tag, new)

    out = FIG_RE.sub(fig_sub, fragment)
    # any bare <img data-chart> left outside a figure
    def bare(m: re.Match) -> str:
        name = m.group(1)
        used.add(name)
        path = os.path.join(CHARTS, name)
        if not os.path.isfile(path):
            missing.append(name)
            print(f"!! MISSING CHART: {name} (image removed)", file=sys.stderr)
            return ""
        if name not in cache:
            cache[name] = encode_chart(path)
        uri, w, h, _ = cache[name]
        return f'<img src="{uri}" alt="" loading="lazy" decoding="async">'

    return IMG_RE.sub(bare, out)


# ----------------------------------------------------------------------------- html helpers
def wrap_tables(fragment: str) -> str:
    return re.sub(r"(<table\b[^>]*>.*?</table>)", r'<div class="tw">\1</div>', fragment, flags=re.S)


def add_copy_buttons(fragment: str) -> str:
    return re.sub(
        r"(<details class=\"code\">\s*<summary>.*?</summary>)",
        r'\1<div class="codebar"><button type="button" class="copy" data-copy>Kopiraj kod</button></div>',
        fragment,
        flags=re.S,
    )


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def collect_toc(fragment: str) -> list[tuple[str, str]]:
    return [(m.group(1), strip_tags(m.group(2))) for m in re.finditer(r'<h2\b[^>]*id="([^"]+)"[^>]*>(.*?)</h2>', fragment, re.S)]


# ----------------------------------------------------------------------------- structure check
VOID = {"img", "br", "hr", "meta", "link", "input", "col", "source", "wbr"}


class Checker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list = []
        self.errors: list[str] = []
        self.ids: collections.Counter = collections.Counter()
        self.hrefs: list[str] = []
        self.heads: list[tuple[int, str]] = []
        self.in_tw = 0
        self.tables = 0
        self.tables_unwrapped = 0
        self.ext: list[str] = []
        self.tw_stack: list[bool] = []
        self.cur_head: int | None = None
        self.buf = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids[a["id"]] += 1
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
        for k in ("src", "href"):
            v = a.get(k, "")
            if re.match(r"https?://", v or "") or (v or "").startswith("//"):
                self.ext.append(f"{tag}:{v}")
        if re.fullmatch(r"h[1-6]", tag):
            self.cur_head = int(tag[1])
            self.buf = ""
        if tag == "table":
            self.tables += 1
            if not any(t == "div" and c == "tw" for t, c in self.stack):
                self.tables_unwrapped += 1
        if tag not in VOID:
            self.stack.append((tag, a.get("class", "")))

    def handle_data(self, data):
        if self.cur_head is not None:
            self.buf += data

    def handle_endtag(self, tag):
        if re.fullmatch(r"h[1-6]", tag) and self.cur_head is not None:
            self.heads.append((self.cur_head, self.buf.strip()))
            self.cur_head = None
        if tag in VOID:
            return
        if not self.stack or self.stack[-1][0] != tag:
            self.errors.append(f"tag mismatch </{tag}> at {self.getpos()} (open: {self.stack[-1][0] if self.stack else None})")
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break
        else:
            self.stack.pop()


def structural_check(doc: str) -> dict:
    c = Checker()
    c.feed(doc)
    res: dict = {"errors": list(c.errors)}
    if c.stack:
        res["errors"].append(f"unclosed tags: {[t for t, _ in c.stack][:8]}")
    dups = [k for k, v in c.ids.items() if v > 1]
    if dups:
        res["errors"].append(f"duplicate ids: {dups}")
    bad = [h for h in c.hrefs if h.startswith("#") and len(h) > 1 and h[1:] not in c.ids]
    if bad:
        res["errors"].append(f"unresolved in-page links: {bad}")
    jumps = []
    prev = 0
    for lvl, text in c.heads:
        if prev and lvl > prev + 1:
            jumps.append(f"h{prev}->h{lvl} at '{text[:40]}'")
        prev = lvl
    if jumps:
        res["errors"].append(f"heading order: {jumps}")
    if c.tables_unwrapped:
        res["errors"].append(f"{c.tables_unwrapped} tables without overflow wrapper")
    bad_ext = [e for e in c.ext if "fonts.googleapis.com" not in e and "fonts.gstatic.com" not in e]
    if bad_ext:
        res["errors"].append(f"external resources: {bad_ext}")
    res.update(
        ids=len(c.ids),
        links=len(c.hrefs),
        in_page_links=sum(1 for h in c.hrefs if h.startswith("#")),
        tables=c.tables,
        headings=len(c.heads),
    )
    return res


def pine_check(doc: str) -> list[dict]:
    out = []
    files = {os.path.basename(p): open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(PINE_DIR, "*.pine"))}
    for m in re.finditer(r'<details class="code">.*?<pre><code>(.*?)</code></pre>', doc, re.S):
        code = html.unescape(m.group(1)).strip()
        hit = [n for n, t in files.items() if t.strip() == code]
        out.append({"lines": code.count("\n") + 1, "matches": hit[0] if hit else None})
    return out


# ----------------------------------------------------------------------------- page shell
CSS = r"""
:root{
  --bg:#f6f3ea; --paper:#fffdf6; --ink:#25262b; --muted:#5d5f68; --line:#d9d3c0; --grid:rgba(70,110,170,.13);
  --accent:#2a4d8f; --accent-ink:#ffffff; --hand:#8a2f1d;
  --good-bg:#e5f3e6; --good-bd:#3d8a4a; --warn-bg:#fdf1d3; --warn-bd:#b7791f; --bad-bg:#fbe4e1; --bad-bd:#b93a2c;
  --teacher-bg:#fff6a8; --example-bg:#e8f0fb; --rule-bg:#f1ecfa; --code-bg:#f0eee6; --th-bg:#ece7d6; --shadow:0 1px 3px rgba(0,0,0,.12);
  --body-font:"Source Serif 4",Georgia,"Times New Roman",serif; --ui-font:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
  --hand-font:"Caveat","Segoe Print","Bradley Hand",cursive; --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#16181d; --paper:#1d2027; --ink:#e7e5de; --muted:#a4a7b1; --line:#383c47; --grid:rgba(140,170,220,.09);
    --accent:#8fb2f0; --accent-ink:#10131a; --hand:#f0b08d;
    --good-bg:#17301d; --good-bd:#58b36a; --warn-bg:#33290f; --warn-bd:#d9a441; --bad-bg:#37191a; --bad-bd:#e0685c;
    --teacher-bg:#3a3716; --example-bg:#1b2840; --rule-bg:#2a2340; --code-bg:#14161b; --th-bg:#2a2e38; --shadow:0 1px 3px rgba(0,0,0,.5);
  }
}
:root[data-theme="dark"]{
  --bg:#16181d; --paper:#1d2027; --ink:#e7e5de; --muted:#a4a7b1; --line:#383c47; --grid:rgba(140,170,220,.09);
  --accent:#8fb2f0; --accent-ink:#10131a; --hand:#f0b08d;
  --good-bg:#17301d; --good-bd:#58b36a; --warn-bg:#33290f; --warn-bd:#d9a441; --bad-bg:#37191a; --bad-bd:#e0685c;
  --teacher-bg:#3a3716; --example-bg:#1b2840; --rule-bg:#2a2340; --code-bg:#14161b; --th-bg:#2a2e38; --shadow:0 1px 3px rgba(0,0,0,.5);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:72px;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.62 var(--body-font);
  background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);
  background-size:24px 24px;
  padding-left:max(16px,env(safe-area-inset-left));padding-right:max(16px,env(safe-area-inset-right));
  padding-bottom:max(24px,env(safe-area-inset-bottom))}
a{color:var(--accent)}
.wrap{max-width:1180px;margin:0 auto;display:block}
.layout{display:block}
.toc-d{display:none}
main{min-width:0}
.page{background:var(--paper);border:1px solid var(--line);border-radius:6px;box-shadow:var(--shadow);padding:20px 18px 28px;margin:12px 0 20px;
  background-image:linear-gradient(90deg,transparent 0,transparent 30px,rgba(185,58,44,.35) 30px,rgba(185,58,44,.35) 31px,transparent 31px);
}
@media (max-width:640px){.page{background-image:none}}
h1,h2,h3,h4{font-family:var(--hand-font);color:var(--hand);line-height:1.15;font-weight:700;margin:1.4em 0 .5em}
h1{font-size:clamp(2.2rem,6vw,3.4rem);margin:.6em 0 .1em}
h2{font-size:clamp(1.9rem,4.5vw,2.5rem);border-bottom:2px dashed var(--line);padding-bottom:.15em}
h3{font-size:clamp(1.5rem,3.4vw,1.85rem)}
h4{font-size:1.35rem}
.sub{color:var(--muted);font-family:var(--ui-font);font-size:.9rem;margin:.2em 0 1em}
.partmark{font-family:var(--hand-font);font-size:1.5rem;color:var(--accent);margin:1.6em 0 0;letter-spacing:.02em}
.partmark span{font-family:var(--ui-font);font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);display:block}
p,li{max-width:72ch}
ul,ol{padding-left:1.3em}
code{font-family:var(--mono);font-size:.86em;background:var(--code-bg);padding:.08em .35em;border-radius:3px;overflow-wrap:anywhere}
.lead{font-size:1.08em}
.small,small{font-size:.82em;color:var(--muted);overflow-wrap:anywhere}
.page{overflow-wrap:break-word}
.term{background:linear-gradient(transparent 60%,rgba(255,214,10,.5) 60%);font-weight:600;padding:0 .1em}
.teacher{background:var(--teacher-bg);border-radius:3px;padding:12px 16px 12px 18px;margin:1.1em 0;box-shadow:2px 3px 0 rgba(0,0,0,.12);
  font-family:var(--hand-font);font-size:1.32rem;line-height:1.35;position:relative;transform:rotate(-.25deg)}
.teacher:before{content:"Učitelj bilježi";display:block;font-family:var(--ui-font);font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:.3em}
.teacher p,.teacher li{max-width:none}
.teacher p{margin:.4em 0}
.example{background:var(--example-bg);border-left:5px solid var(--accent);border-radius:3px;padding:10px 16px;margin:1.1em 0;font-family:var(--ui-font);font-size:.95rem;line-height:1.55}
.example:before{content:"Primjer u eurima";display:block;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:.3em}
.callout{border:1px solid var(--line);border-left:6px solid var(--line);border-radius:3px;padding:10px 16px;margin:1.1em 0;font-family:var(--ui-font);font-size:.95rem;line-height:1.55}
.callout.good{background:var(--good-bg);border-left-color:var(--good-bd)}
.callout.warn{background:var(--warn-bg);border-left-color:var(--warn-bd)}
.callout.bad{background:var(--bad-bg);border-left-color:var(--bad-bd)}
.rule{background:var(--rule-bg);border:1.5px dashed var(--accent);border-radius:4px;padding:10px 16px;margin:1.1em 0;font-family:var(--ui-font);font-size:.95rem}
.rule:before{content:"Točna pravila";display:block;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:.3em}
.rule ol{margin:.3em 0}
.verdict{border:2px solid var(--line);border-radius:4px;padding:10px 16px;margin:1.3em 0;font-family:var(--ui-font);font-size:.97rem;line-height:1.5}
.verdict b:first-child{font-family:var(--hand-font);font-size:1.45rem;color:var(--hand);margin-right:.35em}
.verdict.good{border-color:var(--good-bd);background:var(--good-bg)}
.verdict.warn{border-color:var(--warn-bd);background:var(--warn-bg)}
.verdict.bad{border-color:var(--bad-bd);background:var(--bad-bg)}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:1em 0;max-width:100%;border:1px solid var(--line);border-radius:3px}
table.t{border-collapse:collapse;width:100%;font-family:var(--ui-font);font-size:.82rem;line-height:1.35}
table.t th{background:var(--th-bg);text-align:left;font-weight:700;position:sticky;top:0}
table.t th,table.t td{padding:6px 9px;border-bottom:1px solid var(--line);vertical-align:top}
table.t td{background:transparent}
table.t tbody tr:nth-child(even) td{background:rgba(127,127,127,.07)}
figure.fig{margin:1.4em 0;background:#fff;border:1px solid var(--line);border-radius:4px;padding:8px;box-shadow:var(--shadow)}
figure.fig img{display:block;max-width:100%;height:auto;margin:0 auto}
figure.fig figcaption{font-family:var(--ui-font);font-size:.85rem;line-height:1.45;color:#3d3f47;padding:8px 4px 2px}
details.code{margin:1.2em 0;border:1px solid var(--line);border-radius:4px;background:var(--code-bg)}
details.code summary{cursor:pointer;padding:9px 14px;font-family:var(--ui-font);font-weight:600;font-size:.9rem}
.codebar{display:flex;justify-content:flex-end;padding:0 10px 6px}
button.copy,button.theme,.toc-m summary{font-family:var(--ui-font);font-size:.8rem;border:1px solid var(--accent);background:transparent;color:var(--accent);border-radius:4px;padding:5px 12px;cursor:pointer;min-height:32px}
button.copy:hover,button.theme:hover{background:var(--accent);color:var(--accent-ink)}
details.code pre{margin:0;padding:12px 14px;overflow-x:auto;font-family:var(--mono);font-size:.78rem;line-height:1.5;border-top:1px solid var(--line);max-width:100%}
details.code pre code{background:none;padding:0;overflow-wrap:normal}
section{scroll-margin-top:72px}
.start{background:var(--paper);border:2px solid var(--accent);border-radius:6px;padding:14px 18px;margin:14px 0;font-family:var(--ui-font);font-size:.95rem;line-height:1.55}
.start h2{font-size:2rem;margin:0 0 .3em;border:0}
.start ul{margin:.4em 0}
.toc-m{position:sticky;top:0;z-index:20;background:var(--paper);border:1px solid var(--line);border-radius:0 0 6px 6px;margin:0 0 6px;box-shadow:var(--shadow)}
.toc-m summary{display:block;list-style:none;border:0;padding:10px 14px;min-height:44px;font-weight:600}
.toc-m summary::-webkit-details-marker{display:none}
.toc-m nav{max-height:65vh;overflow:auto;padding:0 14px 12px;font-family:var(--ui-font);font-size:.9rem}
.toc ol,.toc ul{list-style:none;padding:0;margin:.2em 0}
.toc li{margin:.15em 0;max-width:none}
.toc a{text-decoration:none;display:block;padding:3px 6px;border-radius:3px;line-height:1.3}
.toc a:hover,.toc a.on{background:var(--teacher-bg);color:var(--ink)}
.toc .tp{font-family:var(--hand-font);font-size:1.25rem;color:var(--accent);margin:.7em 0 .1em}
.topbar{display:flex;gap:10px;align-items:center;justify-content:space-between;font-family:var(--ui-font);font-size:.8rem;color:var(--muted);margin-top:10px}
footer{font-family:var(--ui-font);font-size:.82rem;color:var(--muted);border-top:2px dashed var(--line);margin-top:2em;padding-top:1em}
@media (min-width:1000px){
  body{font-size:19px}
  .layout{display:grid;grid-template-columns:260px minmax(0,1fr);gap:24px;align-items:start}
  .toc-d{display:block;position:sticky;top:12px;max-height:calc(100vh - 24px);overflow:auto;background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:12px;margin-top:12px;font-family:var(--ui-font);font-size:.82rem;box-shadow:var(--shadow)}
  .toc-m{display:none}
  .page{padding:28px 40px 36px}
}
@media (max-width:640px){
  body{font-size:17px}
  .teacher{font-size:1.2rem;transform:none}
  table.t{font-size:.76rem}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""

JS = r"""
(function(){
  var root=document.documentElement;
  try{var th=localStorage.getItem('mtb-theme');if(th==='light'||th==='dark'){root.setAttribute('data-theme',th);}}catch(e){}
  var tb=document.querySelector('button.theme');
  if(tb){tb.addEventListener('click',function(){
    var cur=root.getAttribute('data-theme');
    if(!cur){cur=(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';}
    var next=cur==='dark'?'light':'dark';
    root.setAttribute('data-theme',next);
    try{localStorage.setItem('mtb-theme',next);}catch(e){}
  });}
  function legacyCopy(text){
    var ta=document.createElement('textarea');ta.value=text;ta.setAttribute('readonly','');
    ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();
    var ok=false;try{ok=document.execCommand('copy');}catch(e){}
    document.body.removeChild(ta);return ok;
  }
  document.querySelectorAll('button[data-copy]').forEach(function(b){
    b.addEventListener('click',function(){
      var d=b.closest('details');var code=d&&d.querySelector('pre code');if(!code)return;
      var text=code.textContent;var label=b.textContent;
      function done(ok){b.textContent=ok?'Kopirano':'Označi i kopiraj ručno';setTimeout(function(){b.textContent=label;},1800);}
      try{
        if(navigator.clipboard&&navigator.clipboard.writeText){
          navigator.clipboard.writeText(text).then(function(){done(true);},function(){done(legacyCopy(text));});
        }else{done(legacyCopy(text));}
      }catch(e){done(legacyCopy(text));}
    });
  });
  var links=[].slice.call(document.querySelectorAll('.toc-d a[href^="#"]'));
  var m=document.querySelector('.toc-m');
  [].forEach.call(document.querySelectorAll('.toc-m a'),function(a){a.addEventListener('click',function(){if(m)m.removeAttribute('open');});});
  if('IntersectionObserver' in window&&links.length){
    var map={};links.forEach(function(a){map[a.getAttribute('href').slice(1)]=a;});
    var io=new IntersectionObserver(function(es){es.forEach(function(e){
      if(e.isIntersecting&&map[e.target.id]){links.forEach(function(a){a.classList.remove('on');});map[e.target.id].classList.add('on');}
    });},{rootMargin:'-10% 0px -80% 0px'});
    Object.keys(map).forEach(function(id){var el=document.getElementById(id);if(el)io.observe(el);});
  }
})();
"""

START_BOX = """
<div class="start" id="pocni-ovdje">
<h2 style="font-size:2rem">Počni ovdje</h2>
<ul>
<li><b>Što je ovo:</b> bilježnica s rezultatima našeg istraživanja swing trgovanja (pozicije od nekoliko dana do tjedana, samo kupnja, bez poluge). Sve je istraživačka simulacija na povijesnim podacima, <b>ne savjet i ne obećanje zarade</b>. Nijedan nalog nije poslan.</li>
<li><b>Ako si potpuni početnik:</b> čitaj redom. Prvo <a href="#p1-0-kako-koristiti">kako koristiti dokument</a>, zatim <a href="#p1-2-trgovanje-od-nule">trgovanje od nule</a> (rječnik s primjerima od 1.000 €), pa <a href="#p1-3-vjerovati">zašto brojkama ne smiješ slijepo vjerovati</a>.</li>
<li><b>Ako želiš samo rezultate:</b> idi na <a href="#p2-uvod-h">pregled strategija na jednoj stranici</a>, zatim na <a href="#p3-plan">plan trgovca</a> i <a href="#p3-otvoreno">što je otvoreno</a>.</li>
<li><b>Što se ne zna (nepotvrđeno):</b> dopuštenja kod brokera, dostupnost američkih ETF-ova malim ulagačima iz EU (KID dokument) i hrvatski porez nisu potvrđeni. Gdje stoji "nepotvrđeno", to znači da to nisam provjerio i ne tvrdim.</li>
<li><b>Najvažniji oprez:</b> test je u razdoblju snažnog rasta tržišta (AI era), pa gotovo svako pravilo za kupnju u njemu izgleda dobro. Kupi-i-drži je u istom razdoblju nadmašio svako pravilo po ukupnom povratu. Rezultati vrijede za to razdoblje.</li>
</ul>
</div>
"""


def build() -> int:
    cache: dict = {}
    missing: list = []
    used: set = set()
    frag_problems: list = []
    body_parts = []
    toc_html_d = []
    toc_html_m = []
    for fname, pid, label, title in PARTS:
        raw = open(os.path.join(DIR, fname), encoding="utf-8").read()
        for t in FORBIDDEN_IN_FRAGMENT:
            if re.search(rf"<{t}[\s>]", raw, re.I):
                frag_problems.append(f"{fname}: forbidden <{t}> tag in fragment")
        toc = collect_toc(raw)
        frag = embed_charts(raw, cache, missing, used)
        frag = wrap_tables(frag)
        frag = add_copy_buttons(frag)
        body_parts.append(
            f'<div class="partmark" id="{pid}"><span>{label}</span>{title}</div>\n<div class="part" data-part="{pid}">\n{frag}\n</div>'
        )
        li = "".join(f'<li><a href="#{i}">{html.escape(t)}</a></li>' for i, t in toc)
        block = f'<div class="tp"><a href="#{pid}">{label}: {title}</a></div><ul>{li}</ul>'
        toc_html_d.append(block)
        toc_html_m.append(block)

    toc_head = '<ul><li><a href="#pocni-ovdje">Počni ovdje</a></li></ul>'
    toc_d = f'<aside class="toc toc-d" aria-label="Sadržaj"><div class="tp">Sadržaj</div>{toc_head}{"".join(toc_html_d)}</aside>'
    toc_m = f'<details class="toc toc-m"><summary>Sadržaj (otvori / zatvori)</summary><nav aria-label="Sadržaj">{toc_head}{"".join(toc_html_m)}</nav></details>'

    doc = f"""<!DOCTYPE html>
<html lang="hr">
<head>
<meta charset="utf-8">
<title>Moj trading bilježnik</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="Bilježnica o swing strategijama na američkim dionicama, kriptu i metalima: što smo testirali, što je uspjelo, što nije. Istraživanje, ne savjet.">
<meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&family=Inter:wght@400;600;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{toc_m}
<div class="layout">
{toc_d}
<main>
<div class="page">
<div class="topbar"><span>Istraživanje, ne savjet. Bez naloga. Podaci do 5. 10. 2026.</span><button type="button" class="theme" aria-label="Promijeni svijetlu i tamnu temu">Svijetlo / tamno</button></div>
<h1>Moj trading bilježnik</h1>
<p class="sub">Swing trgovanje na dionicama, kriptu i zlatu, objašnjeno od nule. Sve brojke dolaze iz projektnih datoteka.</p>
{START_BOX}
{chr(10).join(body_parts)}
<footer>Ovo je istraživanje, a ne ulagački, porezni ni pravni savjet i ne obećava zaradu. Nijedan nalog nije poslan (ni probni ni pravi). Troškovi su modelirani (2,5 bps po strani za dionice, 10 bps po strani za kripto); tečaj EUR/USD, dividende, porezi i minimalna provizija nisu modelirani. Dopuštenja kod brokera, dostupnost ETF-ova (KID) i hrvatski porez su nepotvrđeni. Sastavljeno skriptom <code>scripts/master_assemble.py</code>.</footer>
</div>
</main>
</div>
</div>
<script>{JS}</script>
</body>
</html>
"""
    check = structural_check(doc)
    pine = pine_check(doc)
    pine_bad = [p for p in pine if not p["matches"]]
    if frag_problems:
        check["errors"].extend(frag_problems)
    if pine_bad:
        check["errors"].append(f"{len(pine_bad)} Pine blocks differ from scripts/tradingview files")
    # the JS/CSS contain no script src, but the doc must not reference unused charts as missing
    all_charts = sorted(os.path.basename(p) for p in glob.glob(os.path.join(CHARTS, "*.png")))
    unused = [c for c in all_charts if c not in used]
    data = doc.encode("utf-8")
    size_ok = len(data) <= MAX_BYTES
    if not size_ok:
        check["errors"].append(f"file too large: {len(data)/1e6:.1f} MB")
    with open(OUT, "wb") as f:
        f.write(data)
    report = {
        "output": OUT,
        "size_mb": round(len(data) / 1048576, 2),
        "charts_embedded_unique": len(cache),
        "figures_total": len(re.findall(r"<figure\b", doc)),
        "missing_charts": sorted(set(missing)),
        "unused_charts": unused,
        "pine_blocks": pine,
        "structure": check,
    }
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "pine_blocks"}, ensure_ascii=False, indent=2))
    print(f"pine blocks: {len(pine)}, all equal to files: {not pine_bad}")
    if missing:
        print("!! MISSING CHARTS:", sorted(set(missing)), file=sys.stderr)
    return 1 if check["errors"] else 0


if __name__ == "__main__":
    sys.exit(build())
