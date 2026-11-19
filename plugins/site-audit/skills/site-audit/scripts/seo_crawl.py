#!/usr/bin/env python3
"""Sitemap-based SEO crawl for site audits.

Reads robots.txt and the sitemaps, fetches a sample of the listed pages with a
few parallel requests, and prints what usually turns into an SEO finding:
broken or redirecting URLs in the sitemap, noindex or non-self canonical
pages, missing or duplicate titles and descriptions, missing H1, thin pages,
and leftover pages (test, demo, backup, error pages). It reads the server
HTML only, without running JavaScript.

Usage:
  seo_crawl.py DOMAIN_OR_URL [--out DIR] [--limit 60] [--workers 4] [--items 5] [--sitemap URL ...]

Standard library only. With --out, per-page data goes to DIR/seo_crawl.json.
"""
import argparse
import gzip
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")
LEFTOVER = re.compile(r"(^|[/_.-])(test|testing|demo|sample|backup|bak|old|copy|tmp|temp|staging|dev|"
                      r"draft|lorem|dummy|maintenance|503)([/_.-]|$)", re.I)
ERROR_TITLE = re.compile(r"\b(404|503|not found|service unavailable|maintenance|test page|lorem ipsum|"
                         r"coming soon|under construction)\b", re.I)
FALLBACK_SITEMAPS = ["/sitemap.xml", "/sitemap_index.xml", "/media/sitemap.xml", "/pub/media/sitemap.xml"]
THIN_WORDS = 150
MAX_SITEMAPS, MAX_URLS = 50, 50000


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip",
                                               "Accept-Language": "en-US,en;q=0.9"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(8_000_000)
            status, final, headers = resp.status, resp.geturl(), resp.headers
    except urllib.error.HTTPError as e:
        return {"status": e.code, "final": url, "headers": e.headers or {}, "body": b"",
                "ms": round((time.perf_counter() - start) * 1000)}
    except Exception as e:  # DNS, timeouts, TLS
        return {"status": None, "final": url, "headers": {}, "body": b"", "ms": None, "error": str(e)[:120]}
    if body[:2] == b"\x1f\x8b":
        try:
            body = gzip.decompress(body)
        except OSError:
            pass
    return {"status": status, "final": final, "headers": headers, "body": body,
            "ms": round((time.perf_counter() - start) * 1000)}


def parse_sitemap(body):
    root = ET.fromstring(body)
    kind = root.tag.rsplit("}", 1)[-1]
    locs = []
    for entry in root:
        for child in entry:
            if child.tag.rsplit("}", 1)[-1] == "loc" and child.text:
                locs.append(child.text.strip())
                break
    return kind, locs


def collect(origin, explicit):
    robots = fetch(origin + "/robots.txt")
    text = robots["body"].decode("utf-8", "replace") if robots["status"] == 200 else ""
    rules = urllib.robotparser.RobotFileParser()
    rules.parse(text.splitlines())
    listed = explicit or re.findall(r"(?im)^\s*sitemap:\s*(\S+)", text)
    queue = list(listed) or [origin + p for p in FALLBACK_SITEMAPS]
    fallback = set() if listed else set(queue)
    urls, read, problems, seen = [], [], [], set()
    while queue and len(read) < MAX_SITEMAPS and len(urls) < MAX_URLS:
        sitemap = queue.pop(0)
        if sitemap in seen:
            continue
        seen.add(sitemap)
        r = fetch(sitemap)
        if r["status"] != 200:
            if sitemap not in fallback:
                problems.append(f"{sitemap} → {r['status'] or r.get('error')}")
            continue
        try:
            kind, locs = parse_sitemap(r["body"])
        except ET.ParseError as e:
            problems.append(f"{sitemap} → not valid XML ({e})")
            continue
        read.append(sitemap)
        if sitemap in fallback:
            queue = [q for q in queue if q not in fallback]
        if kind == "sitemapindex":
            queue += locs
        else:
            urls += locs
    if queue:
        problems.append(f"stopped after {len(read)} sitemaps and {len(urls)} URLs; {len(queue)} sitemaps not read")
    if not read:
        problems.append("no sitemap found" + ("" if listed else " (robots.txt lists none; tried the usual paths)"))
    return robots["status"], rules, read, list(dict.fromkeys(urls))[:MAX_URLS], problems


def pick(urls, limit):
    leftovers = [u for u in urls if LEFTOVER.search(urllib.parse.urlsplit(u).path)]
    chosen = leftovers[: max(limit // 4, 1)]
    taken = set(chosen)
    rest = [u for u in urls if u not in taken]
    room = limit - len(chosen)
    if len(rest) <= room:
        chosen += rest
    elif room > 0:
        step = len(rest) / room
        chosen += [rest[int(i * step)] for i in range(room)]
    return chosen, leftovers


class PageParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg"}
    CHROME = {"header", "footer", "nav"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.in_title, self.meta, self.canonical = None, False, {}, None
        self.h1, self.in_h1 = [], 0
        self.skip = self.chrome = self.in_main = 0
        self.words = self.main_words = 0
        self.has_main = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title" and self.title is None:
            self.title, self.in_title = "", True
        elif tag == "meta" and a.get("name", "").lower() in ("description", "robots"):
            self.meta.setdefault(a["name"].lower(), a.get("content", ""))
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonical = self.canonical or a.get("href")
        elif tag == "h1":
            self.in_h1 += 1
            self.h1.append("")
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.CHROME:
            self.chrome += 1
        elif tag == "main":
            self.in_main += 1
            self.has_main = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "h1" and self.in_h1:
            self.in_h1 -= 1
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.CHROME and self.chrome:
            self.chrome -= 1
        elif tag == "main" and self.in_main:
            self.in_main -= 1

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_h1 and self.h1:
            self.h1[-1] += data
        if not self.skip and not self.chrome:
            n = len(data.split())
            self.words += n
            if self.in_main:
                self.main_words += n


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def clip(text, n):
    return text if len(text) <= n else text[: n - 1] + "…"


def norm_url(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


def analyze(url):
    r = fetch(url)
    headers = r["headers"] or {}
    rec = {"url": url, "status": r["status"], "final": r["final"], "ms": r["ms"],
           "x_robots": headers.get("X-Robots-Tag") or ""}
    if r.get("error"):
        rec["error"] = r["error"]
    ctype = headers.get("Content-Type") or ""
    if r["status"] == 200 and "html" in ctype.lower():
        charset = re.search(r"charset=([\w-]+)", ctype)
        parser = PageParser()
        try:
            parser.feed(r["body"].decode(charset.group(1) if charset else "utf-8", "replace"))
        except Exception:
            pass
        rec.update(title=clean(parser.title), description=clean(parser.meta.get("description")),
                   robots=(parser.meta.get("robots") or "").lower(),
                   canonical=urllib.parse.urljoin(r["final"], parser.canonical) if parser.canonical else "",
                   h1=[clean(h) for h in parser.h1],
                   words=parser.main_words if parser.has_main else parser.words)
    return rec


def summarize(origin, robots_status, sitemaps, problems, urls, leftovers, blocked, recs, items):
    out = [f"## SEO crawl of {origin} ({time.strftime('%Y-%m-%d')}; server HTML, no JavaScript)",
           f"robots.txt: {robots_status or 'unreachable'} · sitemaps read: {len(sitemaps)} "
           f"({', '.join(sitemaps[:3])}{' …' if len(sitemaps) > 3 else ''}) · URLs listed: {len(urls)} "
           f"· pages fetched: {len(recs)}"]
    out += [f"Sitemap problem: {p}" for p in problems]
    pages = [r for r in recs if "title" in r]

    def section(label, rows, fmt):
        if rows:
            out.append(f"- {label}: {len(rows)}")
            out.extend(f"    · {fmt(r)}" for r in rows[:items])

    section("in the sitemap but blocked for Googlebot by robots.txt", blocked, lambda u: u)
    section("errors (not 200, or no answer)", [r for r in recs if r["status"] != 200],
            lambda r: f"{r['status'] or r.get('error')} {r['url']}")
    section("sitemap URLs that redirect",
            [r for r in recs if r["status"] == 200 and norm_url(r["final"]) != norm_url(r["url"])],
            lambda r: f"{r['url']} → {r['final']}")
    section("noindex pages in the sitemap",
            [r for r in pages if "noindex" in r["robots"] or "noindex" in r["x_robots"].lower()], lambda r: r["url"])
    section("canonical points to another URL",
            [r for r in pages if r["canonical"] and norm_url(r["canonical"]) != norm_url(r["final"])],
            lambda r: f"{r['url']} → {r['canonical']}")
    section("no canonical tag", [r for r in pages if not r["canonical"]], lambda r: r["url"])
    section("missing title", [r for r in pages if not r["title"]], lambda r: r["url"])
    section("missing meta description", [r for r in pages if not r["description"]], lambda r: r["url"])
    section("missing H1", [r for r in pages if not any(r["h1"])], lambda r: r["url"])
    section("more than one H1", [r for r in pages if len(r["h1"]) > 1], lambda r: f"{len(r['h1'])}× {r['url']}")
    section(f"thin pages (under {THIN_WORDS} words of body text; heuristic)",
            sorted((r for r in pages if r["words"] < THIN_WORDS), key=lambda r: r["words"]),
            lambda r: f"{r['words']} words {r['url']}")
    for field in ("title", "description"):
        groups = defaultdict(list)
        for r in pages:
            if r[field]:
                groups[r[field]].append(r["url"])
        dups = sorted((g for g in groups.items() if len(g[1]) > 1), key=lambda g: -len(g[1]))
        if dups:
            out.append(f"- duplicate {field}s: {sum(len(v) for _, v in dups)} pages in {len(dups)} groups")
            out.extend(f'    · ×{len(v)} "{clip(k, 70)}": {", ".join(v[:2])}' for k, v in dups[:items])
    section("error-like titles", [r for r in pages if ERROR_TITLE.search(r["title"])],
            lambda r: f'"{clip(r["title"], 60)}" {r["url"]}')
    section("leftover-looking URLs in the sitemap (test, demo, backup …)", leftovers, lambda u: u)
    timed = sorted((r for r in recs if r["ms"]), key=lambda r: -r["ms"])
    if timed:
        out.append("- slowest responses: " + " | ".join(f"{r['ms']} ms {r['url']}" for r in timed[:3]))
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("site", help="domain or URL of the site")
    parser.add_argument("--out", help="folder for seo_crawl.json")
    parser.add_argument("--limit", type=int, default=60, help="pages to fetch (default 60)")
    parser.add_argument("--workers", type=int, default=4, help="parallel requests (default 4)")
    parser.add_argument("--items", type=int, default=5, help="examples per issue (default 5)")
    parser.add_argument("--sitemap", nargs="+", help="sitemap URLs to read instead of those in robots.txt")
    args = parser.parse_args()
    start = args.site if re.match(r"https?://", args.site) else "https://" + args.site
    final = urllib.parse.urlsplit(fetch(start)["final"])
    origin = f"{final.scheme}://{final.netloc}"
    robots_status, rules, sitemaps, urls, problems = collect(origin, args.sitemap)
    blocked = [u for u in urls if not rules.can_fetch("Googlebot", u)]
    blocked_set = set(blocked)
    sample, leftovers = pick([u for u in urls if u not in blocked_set], args.limit)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        recs = list(pool.map(analyze, sample))
    report = summarize(origin, robots_status, sitemaps, problems, urls, leftovers, blocked, recs, args.items)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "seo_crawl.json"), "w") as f:
            json.dump({"origin": origin, "sitemaps": sitemaps, "problems": problems, "listed": len(urls),
                       "blocked": blocked, "leftovers": leftovers, "pages": recs}, f, indent=1)
    print(report)


if __name__ == "__main__":
    main()
