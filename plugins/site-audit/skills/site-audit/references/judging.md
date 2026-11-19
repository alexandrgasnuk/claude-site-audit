# Judging the findings

For the main session in Step 4. It covers which performance causes make findings, and which advice makes the team look out of date.

## Performance causes

Each cause below is its own finding, with its own measurement and fix. On a typical shop three or four of them apply. Look at the category and product pages as well as the home page.

- **Server response and page cache:** look at field TTFB, and at the page-cache test in `http_checks.py`, which shows the ad and social parameters that bypass the cache.
  - Field TTFB far worse than lab TTFB means real visitors often miss the cache: through ad parameters, cookies, or a cache that empties too often.
  - The home page cached (HIT) while category or product pages never are (`http_checks.py --pages`) usually means one block on those pages is marked uncacheable (`cacheable="false"` in layout XML), which turns off the page cache for the whole page. Name it as the likely cause; we cannot see the layout from outside.
  - Each page line of `--pages` ends with a verdict. A page that is "✗ not cached" or "✗ looks uncached" on a repeat request, with a slow uncached response, is a finding: every shopper waits for the server on that page type. `cf-cache-status: DYNAMIC` alone proves nothing: Cloudflare does not cache HTML by default, and the shop's own cache may sit behind it.

## Platform version

`http_checks.py` reads `/magento_version`, which shows only the major and minor version, such as `Magento/2.4 (Community)`.
- **2.3 or older:** a High finding. Adobe's lifecycle table starts at 2.4.4, so the line gets no security patches, and Magento shops are a common attack target. Recommend the upgrade to a supported 2.4 release; quote the dates from sources.md.
- **2.4:** the patch level is not visible from outside, so never claim the shop is outdated or vulnerable. At most, add one minor item that the sales team can ask which 2.4 release runs and whether the latest security patches are applied, citing the support dates in sources.md.
- **Hidden (404):** nothing to report; hiding it is good practice.
- Never probe for vulnerabilities, admin paths or exploits. The version endpoint is the only check.
- **JavaScript weight and theme:** look at the number of script files, JavaScript execution and main-thread time, and unused JavaScript, plus `lumaBallast` from the Walkers. It is a finding only when real-user INP or LCP is poor and JavaScript is the measured cause; file counts and lab TBT alone are not. Recommend scoped fixes: load only the jQuery UI modules in use, turn off modules the shop does not use (Pay Later, pickers), and load reCAPTCHA only when a shopper starts filling in a form.
- **Render-blocking scripts and styles:** "Render-blocking requests" in the `psi.py` summary gives the measured cost. The script and stylesheet fields of the Walkers' "Page basics" results show what blocks: scripts without `defer` above or inside the content, or no critical CSS.
- **Third-party tags:** the "Third parties" line of `psi.py` lists tag managers, chat, reviews and A/B tests. Note what each costs in main-thread time, and which can load later or go. Google Tag Manager served from the shop's own domain (server-side GTM, a Cloudflare tag gateway) counts as first-party in Lighthouse, so "Third parties" understates analytics; look for `gtm.js` or `gtag` on the shop's own host.
- **Heavy embeds for hidden content:** video players, maps or widgets that load for a closed popup or tab. Fix them with click-to-load.
- **Images and the LCP element:**
  - When the LCP element is a popup, a newsletter widget or the cookie banner instead of the banner or product photo, that is the finding: the first thing shoppers wait for is an overlay.
  - Check the format and size of the LCP image, `loading=lazy` or a late start on it, a missing `fetchpriority`, and no lazy-loading further down the page.
  - The browser finds an LCP image set as a CSS background only after CSS and layout. The "LCP note" of `psi.py` flags this, and Magento Page Builder banners and sliders work this way, with `data-background-images`. The fix is to render it as an `<img>` (or `<picture>` for separate mobile and desktop images) with `fetchpriority=high`, or to preload it per breakpoint (`<link rel=preload as=image media=… fetchpriority=high>`).
  - A long "Element render delay" in the LCP line means the loaded image waits for something else, such as a slider script.
  - **Missing preload** for the home banner or the main product image, when it is the LCP element and PSI shows a "Resource load delay". Quote the delay as the cost.
- **Layout shifts:** the CLS culprits.
- **Fonts:** look for:
  - formats other than WOFF2;
  - many files or weights;
  - files over 100 KiB, which are often not subset;
  - icon fonts instead of SVG;
  - fonts from a third-party host;
  - no preload for the first-screen font.
- **Delivery basics:** the "Basics" block of `psi.py`: text sent without compression, HTTP/1.1, images over 200 KiB, video weight and HTML size.

Problems of one kind (fonts, images, delivery) make one finding together.

Field data (CrUX) is what customers experience. When lab and field disagree (lab LCP 12 s, field 1.1 s), quote the field value and treat the lab number as a lead. Small Lighthouse items, such as a few KiB of cache lifetime or 10 ms of font display, never stand alone as findings.

## UX and accessibility measurements

The Walkers' measurements (contrast, tap targets, sticky bars, keyboard, labels) are facts with numbers, so they never count as generic advice.

- **On a site with real problems:** they go to `minor`, except a failure on the main path, such as an unreadable "Add to cart" or a menu that cannot be used from the keyboard.
- **On a clean site:** the strongest of them become findings (ACCESSIBILITY or UI), each with its measured value and the WCAG criterion. A short report of measured issues is better than one padded with doubtful ones.
- **Tips on a clean site:** `minor` can hold practical tips for this shop, each tied to something seen or measured on it (a page, an element, a number) and kept to one or two sentences. Generic advice and the "Recommendations to avoid" stay out here too.
- **Sticky bars:** quote the share of the phone screen they take. There is no official limit, so judge it by eye on the screenshot: a bar is a finding when it visibly squeezes the products or covers content.
- **The law in the EU:** the European Accessibility Act covers e-commerce services. Before citing it, check its status under "Not verified" in sources.md.

## Not findings

Normal behaviour of the platform or of e-commerce. A prospect's developer dismisses these, and the rest of the report with them. Each was rejected in a real audit; add new ones as the user rejects them.

- **Filter and sort response time on category pages.** Magento's layered navigation is rarely cached, because the filter combinations are endless, so a 1–2 s response is normal. It counts only when a filter breaks or shows wrong results.
- **Shipping cost shown only after the address.** A shop needs the country and postcode to quote it. A finding needs more: no cost even after a valid address, or no hint of the cost anywhere before checkout while the shop ships at very different rates.
- **"Broken" checkout without the required data.** An error or "no shipping methods" before a valid country and postcode are filled in is how checkout works.
- **Field TTFB as server time.** CrUX TTFB includes DNS, the connection and redirects on the visitor's network. Say "the server takes N s" only from our own timing of an uncached page (`http_checks.py --pages`).
- **Lab-only observations as facts**, such as a script that only Lighthouse saw loading twice. A Walker or the Prover must have seen it too.
- **Search tests in another language or script** than the store's own, such as Latin letters on a Greek store.
- **Overlaps seen at one scroll position only**, such as a floating badge that covers a button for a moment while scrolling. This is a `minor` item at most.
- **A fact checked on the first product card only**, such as "the most expensive product". Check it against the whole category, sorted or filtered, before you build a finding on it.
- **Problems of a fallback store.** Missing reviews, other contacts or slower pages on a default "other countries" store are not problems of the store the prospect sells through.

## Recommendations to avoid

Advice like this makes the team look out of date in front of an expert:

- **JavaScript bundling or merging on Magento** (the built-in option, Magepack or another RequireJS bundler) as the fix for heavy JavaScript. The built-in bundling is known to make pages heavier, and no bundler reduces the code that runs. Recommend the scoped fixes under "JavaScript weight" instead.
- **Rebuilding or migrating the theme** (Luma to Hyvä, a new theme, a headless front end). It is a large project with a large price, too much for a first contact, and the prospect's agency can propose it without us. Recommend fixes that fit the current theme.
- **"Put the tags into one GTM"** when the gtag URLs carry `gtm=` (often `&cx=c&gtm=…`): Google Tag Manager already loads them.
- **AMP pages:** Google stopped requiring AMP for Top Stories in 2021.
- **Meta keywords:** Google has ignored them since 2009.
- **HTTP/2 server push:** Chrome dropped it in 2022.
- **First Input Delay (FID):** INP replaced it as a Core Web Vital in March 2024.
- **"Add a CDN"** for a site that already sits behind one. Look for `x-cache`, `cf-cache-status`, `server: cloudflare` or Fastly headers.
- **Minification or another tiny Lighthouse item** as a finding of its own.
- **Warming the page cache for filter combinations.** On most shops the combinations are too many, so the advice cannot be followed.

When you are not sure a technique is still current, leave it out.
