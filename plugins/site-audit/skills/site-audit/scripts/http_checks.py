#!/usr/bin/env python3
"""HTTP checks for site audits: host redirects, 404 handling, robots.txt, and
whether ad and social parameters (utm_*, gclid, fbclid, ...) bypass the page cache.

Usage:
  http_checks.py DOMAIN_OR_URL [--pages URL ...] [--out DIR]

--pages: more pages (category, product) whose cached and uncached server response
times are measured, so no one has to time them with curl.

Prints a compact summary; with --out it also saves http_checks.json there.
Standard library only.
"""
import argparse
import gzip
import http.client
import json
import os
import random
import re
import ssl
import string
import time
import urllib.parse
from collections import Counter

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate, br"}
CACHE_HEADERS = ("x-cache", "cf-cache-status", "x-magento-cache-debug", "x-proxy-cache", "x-cache-status")
MARKETING = [("utm_*", "utm_source=google&utm_medium=cpc&utm_campaign=audit{r}"), ("gclid", "gclid={r}"),
             ("fbclid", "fbclid={r}"), ("srsltid", "srsltid={r}"), ("msclkid", "msclkid={r}"),
             ("ttclid", "ttclid={r}"), ("random param", "audit{r}=1")]
REDIRECTS = (301, 302, 303, 307, 308)


def rand(n=10):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def request(url, read_body=False):
    """One GET without following redirects, on a new connection, as a first-time visitor (no cookies).
    ttfb_ms includes DNS, TCP and TLS; server_ms is from the request sent to the first byte (server time plus one
    round trip). Requests that read the body ask for gzip only, which the standard library can decode; timing
    requests send a browser's Accept-Encoding, so they hit the same cache copy as Chrome."""
    parts = urllib.parse.urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    if parts.scheme == "https":
        conn = http.client.HTTPSConnection(parts.netloc, timeout=30, context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(parts.netloc, timeout=30)
    headers = dict(HEADERS, **({"Accept-Encoding": "gzip"} if read_body else {}))
    start = time.perf_counter()
    try:
        conn.connect()
        sent = time.perf_counter()
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        now = time.perf_counter()
        ttfb, server = round((now - start) * 1000), round((now - sent) * 1000)
        headers = {k.lower(): v for k, v in resp.getheaders()}
        body = resp.read() if read_body else b""
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        return {"url": url, "status": resp.status, "headers": headers, "ttfb_ms": ttfb, "server_ms": server, "body": body}
    except (OSError, http.client.HTTPException) as e:
        return {"url": url, "status": None, "headers": {}, "ttfb_ms": None, "server_ms": None, "body": b"",
                "error": f"{type(e).__name__}: {e}"[:160]}
    finally:
        conn.close()


def follow(url, limit=8):
    hops = []
    for _ in range(limit):
        r = request(url)
        hops.append(r)
        if r["status"] in REDIRECTS and r["headers"].get("location"):
            url = urllib.parse.urljoin(url, r["headers"]["location"])
        else:
            break
    return hops


def chain_text(hops):
    parts = [hops[0]["url"]]
    for h in hops:
        if h["status"] in REDIRECTS:
            parts.append(f"{h['status']} → {urllib.parse.urljoin(h['url'], h['headers'].get('location', ''))}")
        else:
            parts.append(str(h["status"]) if h["status"] else h.get("error", "error"))
    return " ".join(parts)


def page_title(body):
    m = re.search(rb"<title[^>]*>(.*?)</title>", body or b"", re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1).decode("utf-8", "replace")).strip()[:100] if m else ""


def blanket_disallow(text):
    """True when the group for all crawlers (User-agent: *) has `Disallow: /`."""
    group, in_rules, star_rules = [], False, []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (s.strip() for s in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_rules:
                group, in_rules = [], False
            group.append(value)
        elif key in ("allow", "disallow"):
            in_rules = True
            if "*" in group:
                star_rules.append((key, value))
    return ("disallow", "/") in star_rules


def cache_state(headers):
    values = " ".join(headers.get(h, "") for h in CACHE_HEADERS).upper()
    if "HIT" in values:
        return "HIT"
    # Cloudflare's DYNAMIC means only that the CDN does not cache HTML; the origin cache may still hit
    if any(word in values for word in ("MISS", "PASS", "EXPIRED")):
        return "MISS"
    if headers.get("age", "").isdigit() and int(headers["age"]) > 0:
        return "HIT"
    return "?"


def page_verdict(state, cached_ms, uncached_ms, uncached_state="?"):
    if uncached_state == "HIT":
        return ("? the random parameter did not bypass the cache (the server ignores unknown parameters), "
                "so the uncached time is not valid" + (", the repeat request is cached" if state == "HIT" else ""))
    if state == "HIT":
        return "✓ cached"
    if state == "MISS":
        return "✗ not cached on a repeat request"
    if cached_ms is None or not uncached_ms:
        return "? no answer"
    if cached_ms <= 300 and min(uncached_ms) >= 2 * cached_ms:
        return "✓ looks cached (no cache headers; by time)"
    if cached_ms >= 0.7 * min(uncached_ms) and cached_ms > 500:
        return "✗ looks uncached: the repeat request is as slow as an uncached one (no cache headers; by time)"
    return "? unclear (no cache headers)"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("site", help="domain or URL")
    parser.add_argument("--pages", nargs="+", default=[], help="more pages to time cached and uncached")
    parser.add_argument("--out", help="folder for http_checks.json")
    args = parser.parse_args()
    start_url = args.site if re.match(r"https?://", args.site) else "https://" + args.site
    host = urllib.parse.urlsplit(start_url).netloc.lower()
    bare = host[4:] if host.startswith("www.") else host
    out = [f"## HTTP checks for {host} ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})", "Host variants:"]
    data = {"host": host, "variants": {}}

    finals = []
    for variant in (f"http://{bare}/", f"http://www.{bare}/", f"https://{bare}/", f"https://www.{bare}/"):
        hops = follow(variant)
        last = hops[-1]
        redirects = [h["status"] for h in hops if h["status"] in REDIRECTS]
        flags = []
        if len(redirects) > 1:
            flags.append(f"{len(redirects)} hops")
        if any(s in (302, 303, 307) for s in redirects):
            flags.append("temporary redirect")
        if last["status"] != 200:
            flags.append("does not end in 200")
        else:
            finals.append(last["url"])
        out.append(f"  {chain_text(hops)}" + (f"  ✗ {', '.join(flags)}" if flags else ""))
        data["variants"][variant] = [{k: h.get(k) for k in ("url", "status", "error")} for h in hops]
    ends = Counter(finals)
    if len(ends) == 1:
        out.append(f"  ✓ every working variant ends on {finals[0]}")
    elif ends:
        out.append("  ✗ variants end on different URLs: " + ", ".join(ends))

    main_hops = follow(start_url)
    final = urllib.parse.urlsplit(main_hops[-1]["url"])
    origin = f"{final.scheme}://{final.netloc}"

    missing = f"{origin}/audit-missing-{rand(8)}"
    r = request(missing, read_body=True)
    if r["status"] == 404:
        verdict = "✓ 404"
    elif r["status"] in REDIRECTS:
        verdict = f"✗ {r['status']} redirect to {r['headers'].get('location')} (soft 404)"
    elif r["status"] == 200:
        verdict = "✗ 200 (soft 404)"
    else:
        verdict = str(r["status"] or r.get("error"))
    out.append(f'404 handling: {missing} → {verdict}; title "{page_title(r["body"])}"')
    data["missing_page"] = {"url": missing, "status": r["status"], "title": page_title(r["body"])}

    r = request(f"{origin}/robots.txt", read_body=True)
    if r["status"] == 200:
        text = r["body"].decode("utf-8", "replace")
        sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", text)
        line = f"robots.txt: 200, {len(text.splitlines())} lines; sitemaps: {', '.join(sitemaps) or 'none listed'}"
        if blanket_disallow(text):
            line += "; ✗ Disallow: / for all crawlers"
        out.append(line)
        data["robots"] = {"status": 200, "sitemaps": sitemaps, "blanket_disallow": blanket_disallow(text)}
    else:
        out.append(f"robots.txt: ✗ {r['status'] or r.get('error')}")
        data["robots"] = {"status": r["status"]}

    home = origin + "/"
    first = request(home, read_body=True)
    hdr = first["headers"]
    out.append(f"Home: {first['status']}, HTML {len(first['body']) / 1024:.0f} KiB, "
               f"compression {hdr.get('content-encoding', 'none')}, cache-control: {hdr.get('cache-control', '-')}, "
               f"HSTS: {'yes' if 'strict-transport-security' in hdr else 'no'}, server: {hdr.get('server', '-')}")

    request(home)  # warm the cache copy for a browser's Accept-Encoding
    rows = [("baseline #1", request(home)), ("baseline #2", request(home))]
    for label, template in MARKETING:
        rows.append((label, request(f"{home}?{template.format(r=rand())}")))
    states = [(label, cache_state(r["headers"]), r["server_ms"], r["status"]) for label, r in rows]
    seen = sorted({h for _, r in rows for h in CACHE_HEADERS + ("age",) if h in r["headers"]})
    out.append(f"Page cache (home page, server time without connection setup; cache headers seen: {', '.join(seen) or 'none'}):")
    out.append("  " + " | ".join(f"{label} {state} {ttfb} ms" + (f" (HTTP {status})" if status != 200 else "")
                                 for label, state, ttfb, status in states))
    _, base_state, base_ttfb, _ = states[1]
    if base_state == "MISS":
        out.append("  ✗ the home page is not served from cache even on a repeat request")
    else:
        bypass = [label for label, state, ttfb, _ in states[2:]
                  if (base_state == "HIT" and state == "MISS")
                  or (base_state == "?" and ttfb and base_ttfb and ttfb > 2 * base_ttfb + 300)]
        if bypass:
            out.append(f"  ✗ uncached with: {', '.join(bypass)}. Visitors arriving through such links get the "
                       f"slow, uncached page")
        elif base_state == "?":
            out.append("  ? no cache headers; judged by response time only, no parameter looks uncached")
        else:
            out.append("  ✓ these parameters do not bypass the cache")
    data["cache"] = [{"label": l, "state": s, "server_ms": t, "status": st} for l, s, t, st in states]

    mv = request(origin + "/magento_version", read_body=True)
    text = mv["body"][:200].decode("utf-8", "replace").strip()
    if mv["status"] == 200 and re.match(r"Magento/\d", text):
        out.append(f"Magento version endpoint: {text} (major.minor only; the patch level is not shown)")
        data["magento_version"] = text
    else:
        out.append(f"Magento version endpoint: hidden ({mv['status'] or mv.get('error')})")
        data["magento_version"] = None

    if args.pages:
        out.append("Server response, cached vs uncached (server time without connection setup; cached = 3rd of 3 "
                   "requests; uncached = random parameter, best of 2):")
        data["pages"] = []
        for url in args.pages:
            cached = [request(url) for _ in range(3)][-1]
            uncached = [request(f"{url}{'&' if '?' in url else '?'}audit{rand()}=1") for _ in range(2)]
            times = [u["server_ms"] for u in uncached if u["server_ms"] is not None]
            best = min(times) if times else None
            note = "" if cached["status"] == 200 else f" (HTTP {cached['status'] or cached.get('error')})"
            out.append(f"  {urllib.parse.urlsplit(url).path or '/'}: cached {cache_state(cached['headers'])} "
                       f"{cached['server_ms']} ms{note} | uncached {cache_state(uncached[0]['headers'])} {best} ms"
                       f" (connection setup {cached['ttfb_ms'] - cached['server_ms'] if cached['server_ms'] is not None else '-'} ms)"
                       f" → {page_verdict(cache_state(cached['headers']), cached['server_ms'], times, cache_state(uncached[0]['headers']))}")
            data["pages"].append({"url": url, "cached_ms": cached["server_ms"], "cached_state": cache_state(cached["headers"]),
                                  "uncached_ms": times, "uncached_state": cache_state(uncached[0]["headers"])})

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "http_checks.json"), "w") as f:
            json.dump(data, f, indent=1)
    print("\n".join(out))


if __name__ == "__main__":
    main()
