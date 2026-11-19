#!/usr/bin/env python3
"""PageSpeed Insights for site audits.

Runs PSI with all four Lighthouse categories for every URL and strategy in
parallel, saves the raw JSON and the page screenshots, and prints a compact
summary: scores, lab metrics, real-user (CrUX) field data, the LCP element,
heavy third parties and every failing audit with its top offenders.

Usage:
  psi.py URL [URL ...] --out DIR [--strategy mobile|desktop|both] [--runs N] [--items N] [--full]
  psi.py --from DIR/page-mobile.json [...] [--items N] [--full]   # re-read saved runs

Lab results vary from run to run, so each page and strategy runs --runs times (default 3) and
the run with the median Performance score is kept and summarised; the scores of all runs are
stored in its JSON under "_runs". PSI returns a cached result for the same URL for a minute or
two, so the runs of one page go one after another, --gap seconds apart (default 120), and
identical results are counted once. Different pages still run in parallel.
Desktop runs print scores, metrics and the titles of failing audits; --full adds their details.
Accessibility, best-practices and SEO audits are detailed once per run: on later pages they are
listed by title when an earlier page already showed them (--full shows them every time).
URLs on the tested site are shortened to their path.
Mobile runs also print a Basics block (font and image formats, weights, compression, protocol)
and an LCP note when the LCP image is a CSS background.

API key: $PSI_API_KEY, else "psi_api_key" in ~/.config/site-audit/config.json.
Standard library only.
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CONFIG = os.path.expanduser("~/.config/site-audit/config.json")
CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]
LAB = [("first-contentful-paint", "FCP"), ("largest-contentful-paint", "LCP"),
       ("total-blocking-time", "TBT"), ("cumulative-layout-shift", "CLS"), ("speed-index", "SI")]
FIELD = [("LARGEST_CONTENTFUL_PAINT_MS", "LCP"), ("INTERACTION_TO_NEXT_PAINT", "INP"),
         ("CUMULATIVE_LAYOUT_SHIFT_SCORE", "CLS"), ("FIRST_CONTENTFUL_PAINT_MS", "FCP"),
         ("EXPERIMENTAL_TIME_TO_FIRST_BYTE", "TTFB")]
CRUX = {"FAST": "good", "AVERAGE": "needs improvement", "SLOW": "poor"}
SKIP_GROUPS = {"metrics", "hidden"}
SKIP_MODES = {"notApplicable", "manual", "informative", "error"}


def api_key():
    if os.environ.get("PSI_API_KEY"):
        return os.environ["PSI_API_KEY"]
    try:
        with open(CONFIG) as f:
            return json.load(f).get("psi_api_key")
    except (OSError, ValueError):
        return None


def normalize(url):
    return url if re.match(r"https?://", url) else "https://" + url


def slug(url):
    parts = urllib.parse.urlsplit(url)
    return re.sub(r"[^a-z0-9]+", "-", (parts.netloc + parts.path).lower()).strip("-")[:80] or "page"


def fetch(url, strategy, key, attempts=3):
    query = urllib.parse.urlencode(
        [("url", url), ("strategy", strategy), ("key", key)] + [("category", c) for c in CATEGORIES])
    error = "unknown error"
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(f"{API}?{query}", timeout=240) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            try:
                error = f"HTTP {e.code}: {json.load(e)['error']['message']}"
            except Exception:
                error = f"HTTP {e.code}"
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, OSError) as e:
            error = f"network error: {e}"
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(error)


def ms(v):
    return f"{v / 1000:.1f} s" if v >= 1000 else f"{v:.0f} ms"


def size(v):
    return f"{v / 1048576:.1f} MiB" if v >= 1048576 else f"{v / 1024:.0f} KiB"


def clip(text, n=150):
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def rating(score):
    if score is None:
        return "n/a"
    return "good" if score >= 0.9 else "needs improvement" if score >= 0.5 else "poor"


def node_text(node):
    if not isinstance(node, dict):
        return ""
    selector, label = node.get("selector") or "", node.get("nodeLabel") or ""
    if selector and label and label not in selector:
        return clip(f'{selector} "{label}"', 170)
    return clip(selector or label or node.get("snippet", ""), 170)


def item_text(item):
    if not isinstance(item, dict):
        return clip(item)
    parts = []
    src = item.get("sourceLocation") or item.get("source")
    if isinstance(item.get("url"), str):
        parts.append(clip(item["url"], 130))
    elif isinstance(src, dict) and src.get("url"):
        parts.append(clip(src["url"], 130))
    entity = item.get("entity")
    entity = entity.get("text") if isinstance(entity, dict) else entity
    if entity:
        parts.append(str(entity))
    if isinstance(item.get("node"), dict):
        parts.append(node_text(item["node"]))
    if item.get("description"):
        parts.append(clip(item["description"], 170))
    if item.get("label") and isinstance(item.get("duration"), (int, float)):
        parts.append(f"{item['label']} {ms(item['duration'])}")
    numbers = []
    for key, fmt, label in (("wastedBytes", size, "save"), ("wastedMs", ms, "save"),
                            ("totalBytes", size, "size"), ("transferSize", size, "transfer"),
                            ("mainThreadTime", ms, "main thread"), ("total", ms, "CPU")):
        value = item.get(key)
        if isinstance(value, (int, float)) and value > 0:
            numbers.append(f"{label} {fmt(value)}")
    if numbers:
        parts.append(", ".join(numbers))
    return " — ".join(p for p in parts if p)


def detail_lines(details, limit):
    """Flatten an audit's details into readable lines, at most `limit` per table."""
    if not isinstance(details, dict):
        return []
    lines = []
    if details.get("type") in ("table", "opportunity"):
        lines = [item_text(i) for i in (details.get("items") or [])[:limit]]
    elif details.get("type") == "list":
        for sub in details.get("items") or []:
            kind = sub.get("type")
            if kind in ("table", "opportunity"):
                lines += [item_text(i) for i in (sub.get("items") or [])[:limit]]
            elif kind == "node":
                lines.append("element: " + node_text(sub))
            elif kind == "checklist":
                lines += [f"✗ {c.get('label')}" for c in (sub.get("items") or {}).values()
                          if isinstance(c, dict) and c.get("value") is False]
    return [line for line in lines if line]


def field_line(data):
    for key, scope in (("loadingExperience", "this URL"), ("originLoadingExperience", "whole site")):
        exp = data.get(key) or {}
        metrics = exp.get("metrics") or {}
        if not metrics or exp.get("origin_fallback"):
            continue
        parts = []
        for name, label in FIELD:
            metric = metrics.get(name)
            if metric:
                p = metric["percentile"]
                value = f"{p / 100:.2f}" if label == "CLS" else ms(p)
                parts.append(f"{label} {value} ({CRUX.get(metric.get('category'), 'n/a')})")
        return f"Field (CrUX, real Chrome users, p75 over 28 days, {scope}): " + " · ".join(parts)
    return "Field (CrUX): no real-user data for this URL or site"


TEXT_MIME = re.compile(r"^text/|javascript|json|xml|svg", re.I)
ICON_FONT = re.compile(r"awesome|icomoon|glyphicon|icon|feather|material-?symbols", re.I)
MEDIA_TAGS = ("img", "video", "image", "svg", "picture")


def file_name(url):
    parts = urllib.parse.urlsplit(url)
    return clip(parts.path.rsplit("/", 1)[-1] or parts.netloc, 50)


def listing(rows, limit):
    rows = sorted(rows, key=lambda x: -(x.get("transferSize") or 0))
    text = ", ".join(f"{file_name(x['url'])} {size(x.get('transferSize') or 0)}" for x in rows[:limit])
    return text + (f" (+{len(rows) - limit} more)" if len(rows) > limit else "")


def file_format(item):
    ext = os.path.splitext(urllib.parse.urlsplit(item["url"]).path)[1].lower().lstrip(".")
    mime = (item.get("mimeType") or "").lower().split(";")[0]
    if item.get("resourceType") == "Font":
        if ext in ("woff2", "woff", "ttf", "otf", "eot"):
            return ext
        for fmt in ("woff2", "woff", "ttf", "otf"):
            if fmt in mime:
                return fmt
        return "eot" if "fontobject" in mime else mime or ext or "?"
    sub = mime.split("/")[-1] if "/" in mime else ext
    return {"svg+xml": "svg", "x-icon": "ico", "vnd.microsoft.icon": "ico", "jpg": "jpeg"}.get(sub, sub or "?")


def basics(audits, limit):
    """Delivery basics from the requests Lighthouse recorded: formats, weights, compression, protocol."""
    every = ((audits.get("network-requests") or {}).get("details") or {}).get("items") or []
    items = [x for x in every if str(x.get("url", "")).startswith("http")]
    if not items:
        return []

    def of(kind):
        return [x for x in items if x.get("resourceType") == kind]

    def weight(rows):
        return size(sum(x.get("transferSize") or 0 for x in rows))

    def kinds(rows):
        return ", ".join(f"{k} ×{v}" for k, v in Counter(file_format(x) for x in rows).most_common())

    out, ok = ["Basics (every request of this test):"], []
    fonts = of("Font")
    if fonts:
        hosts = sorted({urllib.parse.urlsplit(x["url"]).netloc for x in fonts})
        line = f"- Fonts: {len(fonts)} files, {weight(fonts)} ({kinds(fonts)}) from {', '.join(hosts)}"
        legacy = [x for x in fonts if file_format(x) != "woff2"]
        heavy = [x for x in fonts if (x.get("transferSize") or 0) > 100 * 1024]
        icons = [x for x in fonts if ICON_FONT.search(file_name(x["url"]))]
        if legacy:
            line += f"; ✗ not WOFF2: {listing(legacy, limit)}"
        else:
            ok.append("fonts WOFF2 only")
        if heavy:
            line += f"; ✗ over 100 KiB: {listing(heavy, limit)}"
        if icons:
            line += f"; icon fonts: {listing(icons, limit)}"
        out.append(line)
    images = of("Image")
    if images:
        line = f"- Images: {len(images)} files, {weight(images)} ({kinds(images)})"
        heavy = [x for x in images if (x.get("transferSize") or 0) > 200 * 1024]
        if heavy:
            line += f"; ✗ over 200 KiB: {listing(heavy, limit)}"
        out.append(line)
    media = of("Media")
    if media:
        out.append(f"- Video and audio: {listing(media, limit)}")
    scripts = of("Script")
    if scripts:
        files, sent = Counter(), Counter()
        for x in scripts:
            host = urllib.parse.urlsplit(x["url"]).netloc
            files[host] += 1
            sent[host] += x.get("transferSize") or 0
        out.append(f"- JavaScript: {len(scripts)} files, {weight(scripts)}; by host: "
                   + ", ".join(f"{h} {files[h]} files {size(b)}" for h, b in sent.most_common(limit)))
    raw = [x for x in items if TEXT_MIME.search(x.get("mimeType") or "") and x.get("statusCode") == 200
           and (x.get("resourceSize") or 0) > 4096 and (x.get("transferSize") or 0) >= 0.9 * x["resourceSize"]]
    if raw:
        out.append(f"- ✗ Text sent without compression: {len(raw)} files: {listing(raw, limit)}")
    else:
        ok.append("text files compressed")
    old = [x for x in items if str(x.get("protocol", "")).lower().startswith("http/1")]
    if old:
        hosts = Counter(urllib.parse.urlsplit(x["url"]).netloc for x in old)
        out.append(f"- ✗ HTTP/1.1: {len(old)} requests from "
                   + ", ".join(f"{h} ×{n}" for h, n in hosts.most_common(limit)))
    else:
        ok.append("HTTP/2 or newer everywhere")
    doc = next(iter(of("Document")), None)
    if doc:
        inline = [x for x in every if x.get("protocol") == "data"]
        out.append(f"- HTML: {size(doc.get('transferSize') or 0)} transferred, "
                   f"{size(doc.get('resourceSize') or 0)} uncompressed"
                   + (f"; data: URIs ×{len(inline)}" if inline else ""))
    if ok:
        out.append("- ✓ " + " · ".join(ok))
    return out


def summarize(data, files, limit, full=False, shown=None):
    """`shown` collects non-performance audits already detailed in this run, so later pages only name them."""
    shown = set() if shown is None else shown
    lr = data["lighthouseResult"]
    audits = lr["audits"]
    strategy = (lr.get("configSettings") or {}).get("formFactor", "?")
    brief = strategy == "desktop" and not full
    url = lr.get("finalDisplayedUrl") or lr.get("requestedUrl")
    out = [f"## {url} — {strategy} (PageSpeed Insights, Lighthouse {lr.get('lighthouseVersion')}, "
           f"{lr.get('fetchTime', '')[:10]})"]
    if lr.get("runWarnings"):
        out.append("Run warnings: " + " | ".join(clip(w, 200) for w in lr["runWarnings"]))
    cats = lr.get("categories", {})
    out.append("Scores: " + " · ".join(
        f"{c.get('title')} {round(c['score'] * 100) if c.get('score') is not None else 'n/a'}"
        for c in cats.values()))
    out.append("Lab: " + " · ".join(
        f"{label} {audits[aid]['displayValue'].replace(chr(160), ' ')} ({rating(audits[aid].get('score'))})"
        for aid, label in LAB if (audits.get(aid) or {}).get("displayValue")))
    out.append(field_line(data))
    if data.get("_runs"):
        out.append(f"Distinct runs: {len(data['_runs'])}, Performance " + " / ".join(str(r["performance"]) for r in data["_runs"])
                   + "; the median run is shown")
    lcp = audits.get("lcp-breakdown-insight") or audits.get("largest-contentful-paint-element") or {}
    lcp_lines = detail_lines(lcp.get("details"), 6)
    if lcp_lines:
        out.append("LCP: " + " | ".join(lcp_lines))
        node = next((s for s in (lcp.get("details") or {}).get("items") or []
                     if isinstance(s, dict) and s.get("type") == "node"), {})
        tag = re.match(r"<\s*([a-z0-9-]+)", (node.get("snippet") or "").lower())
        if tag and tag.group(1) not in MEDIA_TAGS and any("Resource load" in line for line in lcp_lines):
            out.append(f"LCP note: the LCP image is a CSS background of <{tag.group(1)}>, which the browser finds only "
                       "after CSS and layout; check for an image preload (checklist, \"Page basics\")")
    third = audits.get("third-parties-insight") or audits.get("third-party-summary") or {}
    parties = sorted((third.get("details") or {}).get("items") or [],
                     key=lambda i: -(i.get("mainThreadTime") or 0))
    if parties and not brief:
        out.append("Third parties (top by main-thread time): " + " | ".join(item_text(i) for i in parties[:limit]))
    if not brief:
        out += basics(audits, limit)
    failing, seen = [], set()
    for cat_id, cat in cats.items():
        for ref in cat.get("auditRefs", []):
            audit = audits.get(ref["id"]) or {}
            score = audit.get("score")
            if (ref["id"] in seen or ref.get("group") in SKIP_GROUPS
                    or audit.get("scoreDisplayMode") in SKIP_MODES or score is None or score >= 0.9):
                continue
            seen.add(ref["id"])
            failing.append((cat_id, audit))
    if brief:
        titles = [clip(audit.get("title"), 70) for cat_id, audit in failing
                  if cat_id == "performance" or audit.get("id") not in shown]
        out.append("Failing audits (titles only; --full for details; other categories as on mobile): "
                   + "; ".join(titles))
    else:
        out.append("Failing audits:")
        repeated = []
        for cat_id, audit in failing:
            if cat_id != "performance" and not full:
                if audit.get("id") in shown:
                    repeated.append(clip(audit.get("title"), 70))
                    continue
                shown.add(audit.get("id"))
            head = f"- [{cat_id}] {audit.get('title')}"
            if audit.get("displayValue"):
                head += f" — {audit['displayValue'].replace(chr(160), ' ')}"
            savings = {k: v for k, v in (audit.get("metricSavings") or {}).items() if v}
            if savings:
                head += " (est. savings " + ", ".join(
                    f"{k} {v:.2f}" if k == "CLS" else f"{k} {ms(v)}" for k, v in savings.items()) + ")"
            out.append(head)
            if audit.get("id") != "lcp-breakdown-insight" or full:  # the LCP line above already shows it
                out += [f"    · {line}" for line in detail_lines(audit.get("details"), limit)]
        if repeated:
            out.append("- also failing, details on an earlier page: " + "; ".join(repeated))
    if files:
        out.append("Saved: " + ", ".join(files))
    origin = re.match(r"https?://[^/]+", url or "")
    text = "\n".join(out[:1] + [line.replace(origin.group(0) + "/", "/") for line in out[1:]] if origin else out)
    return text


def save_screenshots(data, base):
    lr = data["lighthouseResult"]
    sources = [(((lr.get("audits") or {}).get("final-screenshot") or {}).get("details") or {}).get("data"),
               ((lr.get("fullPageScreenshot") or {}).get("screenshot") or {}).get("data")]
    saved = []
    for uri, name in zip(sources, ("final", "fullpage")):
        if not uri or "," not in uri:
            continue
        head, payload = uri.split(",", 1)
        ext = "jpg" if "jpeg" in head else head.split("/")[1].split(";")[0]
        path = f"{base}-{name}.{ext}"
        with open(path, "wb") as f:
            f.write(base64.b64decode(payload))
        saved.append(path)
    return saved


def _try_fetch(url, strategy, key):
    try:
        return fetch(url, strategy, key)
    except RuntimeError as e:
        return str(e)


def perf_score(data):
    return ((data["lighthouseResult"].get("categories") or {}).get("performance") or {}).get("score")


def lab_value(data, audit_id):
    return ((data["lighthouseResult"].get("audits") or {}).get(audit_id) or {}).get("numericValue")


def run_key(data):
    lr = data["lighthouseResult"]
    return (lr.get("fetchTime"), perf_score(data), lab_value(data, "largest-contentful-paint"),
            lab_value(data, "total-blocking-time"))


def median_run(runs):
    """The run with the median Performance score, with every run's numbers stored under "_runs".
    A cached repeat of an earlier run (same fetchTime and numbers) is counted once."""
    unique = list({run_key(r): r for r in runs}.values())
    scored = sorted((r for r in unique if perf_score(r) is not None), key=perf_score)
    if not scored:
        return runs[0]
    chosen = scored[(len(scored) - 1) // 2]
    chosen["_runs"] = [{"performance": round(perf_score(r) * 100), "lcp_ms": lab_value(r, "largest-contentful-paint"),
                        "tbt_ms": lab_value(r, "total-blocking-time"), "cls": lab_value(r, "cumulative-layout-shift"),
                        "fetchTime": r["lighthouseResult"].get("fetchTime")} for r in scored]
    return chosen


def run(job):
    url, strategy, key, out_dir, runs, gap = job
    results, errors = [], []
    for i in range(runs):
        if i:
            time.sleep(gap)  # past PSI's result cache, so the next run is a new test
        outcome = _try_fetch(url, strategy, key)
        (results if isinstance(outcome, dict) else errors).append(outcome)
    if not results:
        return url, strategy, None, f"FAILED: {errors[0]}"
    data = median_run(results)
    base = os.path.join(out_dir, f"{slug(url)}-{strategy}")
    with open(base + ".json", "w") as f:
        json.dump(data, f)
    files = [base + ".json"] + save_screenshots(data, base)
    return url, strategy, data, [os.path.basename(p) for p in files]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("urls", nargs="*", help="pages to test (scheme optional)")
    parser.add_argument("--out", help="folder for raw JSON, screenshots and summary.md")
    parser.add_argument("--strategy", choices=["mobile", "desktop", "both"], default="both")
    parser.add_argument("--runs", type=int, default=3, help="runs per page and strategy; the median is kept (default 3)")
    parser.add_argument("--gap", type=int, default=120, help="seconds between runs of one page (default 120)")
    parser.add_argument("--items", type=int, default=3, help="offenders listed per failing audit (default 3)")
    parser.add_argument("--from", dest="saved", nargs="+", metavar="JSON", help="re-read saved raw results")
    parser.add_argument("--full", action="store_true", help="details of failing audits for desktop runs too")
    args = parser.parse_args()

    if args.saved:
        reports, shown = [], set()
        for path in args.saved:
            with open(path) as f:
                reports.append(summarize(json.load(f), [], args.items, args.full, shown))
        print("\n\n".join(reports))
        return
    if not args.urls or not args.out:
        parser.error("give one or more URLs and --out")
    key = api_key()
    if not key:
        sys.exit(f'No PageSpeed Insights API key. Set PSI_API_KEY or put {{"psi_api_key": "..."}} in {CONFIG}. '
                 "Free key: Google Cloud console > APIs & Services > Credentials, with the PageSpeed Insights API enabled.")
    os.makedirs(args.out, exist_ok=True)
    strategies = ["mobile", "desktop"] if args.strategy == "both" else [args.strategy]
    jobs = [(normalize(u), s, key, args.out, max(1, args.runs), max(0, args.gap)) for u in args.urls for s in strategies]
    with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as pool:
        results = list(pool.map(run, jobs))
    shown = set()
    report = "\n\n".join(f"## {url} — {strategy}\n{extra}" if data is None
                           else summarize(data, extra, args.items, args.full, shown)
                           for url, strategy, data, extra in results)
    with open(os.path.join(args.out, "summary.md"), "a") as f:
        f.write(report + "\n\n")
    print(report)


if __name__ == "__main__":
    main()
