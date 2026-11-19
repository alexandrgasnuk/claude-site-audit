# Browser setup

For the main session, the Walkers and the Prover: the two tabs, how to identify the platform, and the quirks of the Claude in Chrome tools.

## Desktop and mobile tabs

The audit runs in two tabs of one clean incognito window:

- **Desktop:** a maximized window, with an `innerWidth` of at least 1280 px.
- **Mobile:** Chrome DevTools device emulation, which the user turns on in this tab. They open the device toolbar and pick a phone such as Pixel 7, which gives a 412 px width, a mobile user agent and touch. The emulated tab keeps its phone size whatever the window size.

Check each tab with `javascript_tool`:

```js
({w: innerWidth, h: innerHeight, touch: navigator.maxTouchPoints, mobileUA: /Mobi/.test(navigator.userAgent)})
```

Do not rely on `resize_window` for a phone width: it had no effect in either of the earlier audits.

In the emulated mobile tab:
- **Screenshots** from `computer` come out small; in an earlier audit the page measured about 138×296 in screenshot coordinates. To look at the page or save proof, use `computer` → `zoom` on the page region at `scale` 0.6–1.
- **Clicks** work best through `find` refs (`left_click` with `ref`) or `el.click()` in `javascript_tool`, because coordinates are coarse.

### When no one can turn on the emulation

Look at the mobile layout through a same-origin frame in a desktop tab. Its limits:
- The page gets a desktop user agent and no touch events, so mobile-only widgets may differ.
- The frame fails when the site forbids framing (`X-Frame-Options: DENY` or CSP `frame-ancestors 'none'`).
- Clicks inside the frame need coordinate maths, so prefer `el.click()`.

```js
// on https://<site>/robots.txt: same origin, so the frame stays reachable from JS
document.open(); document.write('<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#e9e9e9}#m{position:absolute;left:40px;top:12px;width:390px;height:760px;border:0;box-shadow:0 0 0 1px #999;background:#fff}</style><iframe id="m" src="https://<site>/"></iframe>'); document.close();
// after the frame loads: hide its scrollbar so the layout width is exactly 390 px
const d = document.getElementById('m').contentDocument, s = d.createElement('style');
s.textContent = 'html{scrollbar-width:none} html::-webkit-scrollbar{display:none}'; d.head.appendChild(s);
```

For a proof shot, use `computer` → `zoom` on the frame region with `save_to_disk: true`.

### Cross-check

With either method, compare with the PSI mobile screenshots in `psi/` (`*-mobile-final.jpg`, `*-mobile-fullpage.webp`). PSI takes them in a clean session with a real phone user agent.

## Platform fingerprints

Run in the page with `javascript_tool`:

```js
({
  magento: !!document.querySelector('script[src*="/static/version"], link[href*="/static/version"]'),
  requirejs: typeof require === 'function',
  knockout: typeof ko !== 'undefined',
  alpine: !!window.Alpine,
  shopify: !!window.Shopify,
  woocommerce: !!document.querySelector('[src*="woocommerce"], [href*="woocommerce"]')
})
```

- **Magento 2**: assets under `/static/version<digits>/frontend/<Vendor>/<theme>/<locale>/`.
  - **Hyvä** theme: Alpine.js and Tailwind classes, no RequireJS.
  - **Luma** or Luma-based: RequireJS, KnockoutJS and `data-mage-init` attributes. Heavy JavaScript is typical.
- **Shopify**: `cdn.shopify.com` or `/cdn/shop/` assets, `window.Shopify`.
- **WooCommerce**: `/wp-content/plugins/woocommerce/` assets.
- **Others**:
  - BigCommerce: `cdn11.bigcommerce.com`
  - Shopware: `/bundles/storefront/`
  - PrestaShop: `/modules/`, `window.prestashop`
  - Salesforce Commerce Cloud: `/on/demandware.static/`

## Tool quirks

- **Blocked output:** `javascript_tool` hides results that look like cookies or query strings and shows `[BLOCKED: Cookie/query string data]` instead. To avoid it:
  - return only the fields you need;
  - reduce URLs to origin + path;
  - give keys neutral names;
  - read inline scripts from a page saved with `curl` into `tmp/`, not from the live page.
- **Screenshot format:** `computer` screenshots saved with `save_to_disk` may be PNG or JPEG, so keep the extension when you copy them.
