# Audit checklist

For the Walkers. This is a map of where problems usually hide, not a form to fill in: note what fails, and skip what does not apply to this site.

## Page basics (browser)

Run this with `javascript_tool` on home, category and product, right after a fresh load in the mobile tab. It returns only file names and hosts, so the tool's output filter lets it through.

```js
(() => {
  const vh = innerHeight;
  const file = u => { try { return new URL(u, location).pathname.split('/').pop().slice(0, 50) || '/'; } catch (e) { return '?'; } };
  const host = u => { try { return (u && new URL(u, location).hostname) || 'inline'; } catch (e) { return '?'; } };
  const visible = el => el.getClientRects().length > 0;
  const top = el => el.getBoundingClientRect().top + scrollY;
  const imgs = [...document.images].filter(i => i.currentSrc || i.src);
  const shown = imgs.filter(visible);
  const isJs = s => !s.type || /^(text|application)\/(x-)?(java|ecma)script$/i.test(s.type);
  const sync = [...document.querySelectorAll('script[src]')].filter(s => isJs(s) && !s.async && !s.defer);
  const main = document.querySelector('main, #maincontent, [role="main"]');
  const footer = document.querySelector('footer, .page-footer');
  const beforeEnd = s => footer ? !!(s.compareDocumentPosition(footer) & Node.DOCUMENT_POSITION_FOLLOWING)
    : !!main && !!(s.compareDocumentPosition(main) & (Node.DOCUMENT_POSITION_FOLLOWING | Node.DOCUMENT_POSITION_CONTAINS));
  const cap = a => a.length > 8 ? [...a.slice(0, 8), `+${a.length - 8} more`] : a;
  const backgrounds = [...document.querySelectorAll('body *')].filter(el => {
    const r = el.getBoundingClientRect();
    return r.top < vh && r.bottom > 0 && r.width * r.height > innerWidth * vh * 0.15
      && getComputedStyle(el).backgroundImage.includes('url(');
  });
  return {
    images: imgs.length,
    lazyInFirstScreen: shown.filter(i => top(i) < vh && i.loading === 'lazy').map(i => file(i.currentSrc || i.src)),
    eagerBelowFold: shown.filter(i => top(i) > vh * 1.5 && i.loading !== 'lazy').length,
    hiddenButEager: imgs.filter(i => !visible(i) && i.loading !== 'lazy').map(i => file(i.currentSrc || i.src)).slice(0, 8),
    bigBackgroundsInFirstScreen: backgrounds.map(el => String(el.className || el.tagName).slice(0, 60)),
    preloads: [...document.querySelectorAll('link[rel~="preload"]')].map(l => `${l.as} ${file(l.href || (l.imageSrcset || '').trim().split(/\s/)[0])}${l.media ? ` (${l.media})` : ''}${l.fetchPriority === 'high' ? ' high' : ''}`),
    fetchpriorityHigh: [...document.querySelectorAll('[fetchpriority="high"]')].map(el => `${el.tagName.toLowerCase()} ${file(el.currentSrc || el.src || el.href || '')}`),
    firstScreenImages: shown.filter(i => top(i) < vh).slice(0, 4).map(i => `${file(i.currentSrc || i.src)} ${i.naturalWidth}px`),
    preconnects: [...document.querySelectorAll('link[rel~="preconnect"], link[rel~="dns-prefetch"]')].map(l => `${l.rel} ${host(l.href)}`),
    stylesheetsInHead: document.head.querySelectorAll('link[rel~="stylesheet"]:not([media="print"])').length,
    inlineCssKiB: Math.round([...document.querySelectorAll('style')].reduce((n, s) => n + s.textContent.length, 0) / 1024),
    syncScriptsInHead: cap(sync.filter(s => document.head.contains(s)).map(s => file(s.src))),
    syncScriptsInContent: cap(sync.filter(s => !document.head.contains(s) && beforeEnd(s)).map(s => file(s.src))),
    inlineJsInHeadKiB: Math.round([...document.head.querySelectorAll('script:not([src])')].filter(isJs).reduce((n, s) => n + s.textContent.length, 0) / 1024),
    iframes: [...document.querySelectorAll('iframe')].map(f => host(f.src || f.dataset.src || '')),
    videos: [...document.querySelectorAll('video')].map(v => `autoplay ${v.autoplay}, preload ${v.preload}, poster ${!!v.poster}`),
    dpr: devicePixelRatio, viewportWidth: innerWidth,
    lumaBallast: Object.fromEntries(Object.entries({
      jqueryUi: /jquery\/ui|jquery-ui-modules/, payLater: /paylater|pay-later|braintree/i,
      colorPicker: /spectrum|colorpicker/i, timepicker: /timepicker/i, recaptcha: /recaptcha/i
    }).map(([k, re]) => [k, performance.getEntriesByType('resource').filter(r => re.test(r.name)).length]).filter(([, n]) => n))
  };
})()
```

What the result shows:
- `lazyInFirstScreen`: first-screen images that wait for lazy-loading. On the LCP image, this delays LCP.
- `eagerBelowFold`: images far down the page that load at once, which phones pay for up front.
- `hiddenButEager`: hidden images that still download, such as the desktop copy of a Page Builder image on a phone.
- `bigBackgroundsInFirstScreen`: a CSS background in the first screen, which the browser finds late. With no matching image in `preloads`, it is a lead for the LCP.
- `preloads`: look for a missing first-screen font, or preloads of files the first screen does not use.
- `firstScreenImages`: the images actually shown in the first screen. Compare them with `preloads`: a preloaded image that is not among them (another size, or jpg/png while the page shows WebP, as WebP modules do) is downloaded twice. A preload `media` that does not match the `<picture>` breakpoints has the same effect. On mobile, an image much wider than `viewportWidth` × `dpr` is the desktop banner sent to phones.
- `lumaBallast`: on Luma themes, files loaded for features the page does not use: jQuery UI loaded globally (dozens of files), PayPal or Braintree "Pay Later", colour and time pickers, reCAPTCHA on a page without a form. Note the counts; they are evidence for the JavaScript-weight finding.
- `preconnects`: more than four, or none for the hosts of first-screen files (image CDN, fonts).
- `syncScriptsInHead`, `syncScriptsInContent`: scripts without `defer` or `async`, in `<head>` or before the end of the content. At each one the browser stops building the page until the script downloads and runs, so nothing below it appears meanwhile.
- `inlineJsInHeadKiB`: large inline scripts in `<head>` hold the browser in the same way while they run.
- `stylesheetsInHead`, `inlineCssKiB`: several stylesheets and no inline critical CSS hold back the first paint.
- `iframes`, `videos`: players and maps that load before anyone asks for them, and autoplay video without a poster.

## UX and accessibility measurements (browser)

Numbers instead of advice: "Add to cart has a contrast of 2.8:1, below the 4.5:1 of WCAG" holds up in front of a prospect, "check your contrast" does not. Run this on home, category, product and cart, in the mobile tab (tap targets are judged there) and once on home in the desktop tab.

```js
(() => {
  const ctx = Object.assign(document.createElement('canvas'), { width: 1, height: 1 }).getContext('2d', { willReadFrequently: true });
  const rgba = css => { ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = '#000'; ctx.fillStyle = css; ctx.fillRect(0, 0, 1, 1); return [...ctx.getImageData(0, 0, 1, 1).data]; };
  const lum = c => c.slice(0, 3).map(v => (v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4).reduce((n, v, i) => n + v * [0.2126, 0.7152, 0.0722][i], 0);
  const back = el => {
    for (let e = el; e; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.backgroundImage !== 'none') return null;
      const c = rgba(s.backgroundColor);
      if (c[3] > 230) return c;
    }
    return [255, 255, 255, 255];
  };
  const visible = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && +s.opacity > 0.1; };
  const label = el => (el.innerText || el.value || el.getAttribute('aria-label') || el.placeholder || el.title || el.className || el.tagName).toString().trim().replace(/\s+/g, ' ').slice(0, 30);
  const contrast = el => {
    const b = back(el); if (!b) return null;
    const s = getComputedStyle(el), f = rgba(s.color), L = [lum(f), lum(b)].sort((x, y) => y - x);
    const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.66 && +s.fontWeight >= 700);
    return { ratio: Math.round((L[0] + 0.05) / (L[1] + 0.05) * 10) / 10, need: large ? 3 : 4.5 };
  };
  const fails = els => [...new Map(els.filter(visible).map(el => [label(el), el])).entries()]
    .map(([t, el]) => [t, contrast(el)]).filter(([, c]) => c && c.ratio < c.need)
    .sort((a, b) => a[1].ratio - b[1].ratio).slice(0, 6).map(([t, c]) => `${t}: ${c.ratio}:1 (needs ${c.need})`);
  const buttons = [...document.querySelectorAll('button, [type=submit], [role=button], a.action, a.btn, a[class*=button]')];
  const texts = [...document.querySelectorAll('p, li, a, span, label, small, h1, h2, h3, h4, td, dd')]
    .filter(el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).slice(0, 600);
  const inText = el => el.tagName === 'A' && getComputedStyle(el).display === 'inline' && el.closest('p, li, td, dd');
  const small = [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [role=button]')]
    .filter(el => visible(el) && !inText(el)).map(el => [el, el.getBoundingClientRect()])
    .filter(([, r]) => r.width < 24 || r.height < 24);
  const fields = [...document.querySelectorAll('input:not([type=hidden]):not([type=submit]):not([type=button]), select, textarea')]
    .filter(el => visible(el) && !el.labels.length && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby') && !el.title);
  const focusables = [...document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])')].slice(0, 3);
  return {
    lowContrastButtons: fails(buttons),
    lowContrastText: fails(texts),
    smallTapTargets: { count: small.length, examples: small.slice(0, 6).map(([el, r]) => `${label(el)} ${Math.round(r.width)}×${Math.round(r.height)}`) },
    fieldsWithoutLabel: fields.slice(0, 6).map(el => el.name || el.id || el.placeholder || el.type),
    imagesWithoutAlt: [...document.images].filter(i => visible(i) && !i.hasAttribute('alt')).length,
    lang: document.documentElement.lang || null,
    skipLink: focusables.some(el => /^#/.test(el.getAttribute('href') || '') && /skip|content|main/i.test(el.textContent + el.getAttribute('href')))
  };
})()
```

What the result shows:
- `lowContrastButtons`, `lowContrastText`: below 4.5:1 for normal text and 3:1 for large text (WCAG 2.2 AA, 1.4.3). Elements on a background image or gradient are skipped; judge those by eye.
- `smallTapTargets`: controls under 24×24 px (WCAG 2.2 AA, 2.5.8), links inside running text excluded. A small control with enough empty space around it still passes, so check the examples on screen before recording them.
- `fieldsWithoutLabel`: fields that screen readers announce without a name. A placeholder alone disappears while typing.
- `imagesWithoutAlt`, `lang`, `skipLink`: missing alt attributes, a missing page language, and no "Skip to content" link as the first stop of the Tab key.

**Sticky bars.** In the mobile tab, scroll to the middle of a category and a product page, then run this. It lists bars fixed to the top or bottom of the screen and the share of the screen height each takes:

```js
(() => [...document.querySelectorAll('body *')].filter(el => {
  const s = getComputedStyle(el); if (s.position !== 'fixed' && s.position !== 'sticky') return false;
  const r = el.getBoundingClientRect();
  return r.width >= innerWidth * 0.8 && r.height > 0 && r.bottom > 0 && r.top < innerHeight && (r.top <= 5 || r.bottom >= innerHeight - 5);
}).filter((el, i, all) => !all.some(o => o !== el && o.contains(el))).map(el => {
  const r = el.getBoundingClientRect();
  return `${r.top <= 5 ? 'top' : 'bottom'} ${String(el.className || el.tagName).slice(0, 40)} ${Math.round(r.height)}px, ${Math.round(r.height / innerHeight * 100)}% of the screen`;
}))()
```

Note also the opposite: no way back to the menu, search or cart on a long page, when the header scrolls away and nothing replaces it.

**Keyboard** (desktop tab, home page, part 1): click an empty spot at the top of the page, then press Tab a few times with `computer` and take a `scale: 0.5` screenshot after each. Note whether the focused element is visibly marked, whether a skip link appears, and whether the main menu opens with Enter or the arrow keys. This tells which element has the focus and how it is marked:

```js
(() => { const el = document.activeElement, s = getComputedStyle(el); return `${el.tagName} "${(el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 30)}" outline ${s.outlineStyle} ${s.outlineWidth}, box-shadow ${s.boxShadow !== 'none'}`; })()
```

## Every page

- **Errors:** read console errors with `read_console_messages` (errors only) and failed requests with `read_network_requests` (4xx, 5xx, failed). Note when each appears and what stops working.
- **Layout shifts:** while the page loads and while scrolling, look for late banners, fonts, review widgets and cookie bars that push content.
- **Mobile:** look for:
  - horizontal scrolling;
  - overlapping or cut-off elements;
  - tap targets that are too small;
  - sticky bars covering content;
  - elements that flash open before scripts finish (search boxes, menus).
- **Accessibility basics:** measure them with "UX and accessibility measurements" above.
- **Time-dependent widgets:** for chat, opening hours and promotions, note the site's local time, since their state may differ during the sales call.

## Header and menu

- Hover menus that open the moment the cursor passes over them, close too fast, or cannot be used by touch.
- A search box that is visible and usable on mobile.
- Cart and account icons with clear counters.

## Home

- The LCP element: its weight, its format, and `loading=lazy` on it.
- **Banner preload:** when the first screen is a banner or slider image, look in `preloads` and `fetchpriorityHigh` for it. Note whether it is preloaded, whether mobile and desktop get their own image (`media` on the preload), and the file names, so they can be matched with the LCP element.
- Product widgets and carousels: out-of-stock items, broken images, missing prices.
- Promotions and sliders: expired campaigns, auto-rotation too fast to read.

## Category

- **Out-of-stock products:** on the first page of a large category, count the cards marked out of stock, sold out or unavailable, and note their positions. Mixed in among available products, they take the best slots and frustrate shoppers.
- **Filters:** they work, combine, show counts, and survive the Back button.
- **Navigation:** sorting, pagination or infinite scroll, and a visible product count.
- **Product cards:** image weight, price, stock, add to cart from the list, compare and wishlist.
- **Comparison:** large categories of similar products that shoppers can compare only by opening each one. Record this as a feature idea.

## Product

- **Main image preload:** `preloads` should list the first gallery image, the usual LCP element of a product page, and it should match the file in `firstScreenImages`. Note the theme (Hyvä, Luma or other) next to the result.
- Gallery and zoom; variants and swatches that update price and stock.
- Add-to-cart feedback (mini-cart, message) and where it appears on a phone screen; delivery and stock information.
- Reviews: the widget layout and styled form fields.
- Layout shifts from reviews, prices or recommendation blocks.
- Purchase options the shop lacks, such as express checkout, subscriptions or quote requests. Record them as feature ideas; the main session looks for the evidence.

## Search

- Autocomplete speed and design, typo tolerance, and a helpful no-results page.
- Terms customers would use for the shop's own product types: a condition, a use, a common misspelling. When one finds nothing, check whether the shop's product pages use that word. That is the proof.

## Cart and checkout (guest)

- **Cart:** the layout, where the totals sit, editing quantities, the coupon field.
- **Checkout:** what a guest sees after "Proceed to Checkout", the number of steps, and payment and shipping methods with clear names. Fill in the test data from your rules (main country, valid postcode and address, "Test Audit", `audit-test@example.com`) so that shipping and payment methods appear, and walk up to the final button. Never press "Place order" or "Pay", enter no card details and no password, and leave terms and consent checkboxes unticked.
- An error or "no shipping methods" counts only after the country and a valid postcode are filled in.
- **Account-only checkout:** this is usually deliberate. Record what a guest sees; the main session decides.

## 404 and errors

- `/<random-string>` should show a styled page with search and links, and answer with HTTP 404. Anything else is a soft 404.

## Links and trust

- External links (social, manufacturers) that take customers away mid-purchase.
- Broken links in the menu and footer.

## Technical SEO

`http_checks.py` covers host redirects, the 404 status, robots.txt and the page-cache test. `seo_crawl.py` covers the pages listed in the sitemap. In the browser, check what the scripts cannot judge:

- **A category with a filter applied:** filtered pages that people search for (brand + category, for example) should be indexable with their own title. Useless combinations should stay out of the index.
- **hreflang** on multi-language sites.

This snippet shows the tags as the page ends up with them:

```js
({
  title: document.title,
  description: document.querySelector('meta[name="description"]')?.content,
  robots: document.querySelector('meta[name="robots"]')?.content,
  canonical: document.querySelector('link[rel="canonical"]')?.href,
  hreflang: [...document.querySelectorAll('link[rel="alternate"][hreflang]')].map(l => l.hreflang)
})
```

## Operations

- Downtime or maintenance pages during the audit (note the time), mixed content, certificate problems.
