# Sources

These sources were already checked for `why` and `evidence`. Each entry quotes the wording found on the page, so quote from here instead of searching again.

To add a source for a claim that is not covered here:
1. Find it with WebSearch.
2. Confirm the wording with WebFetch on the page itself.
3. Add it below with the date you checked it.

Re-check a source before quoting it if it was checked more than about a year ago.

## Speed

- **TTFB thresholds:** "Good TTFB values are 0.8 seconds or less" and "poor values are greater than 1.8 seconds". TTFB comes before FCP and LCP. https://web.dev/articles/ttfb (checked 2026-11-16)
- **CLS thresholds:** good is 0.1 or less, poor is above 0.25. https://web.dev/articles/cls (checked 2026-11-16)

## Checkout and conversion

- **Forced account creation:** 18% of shoppers who abandoned an order named "The site wanted me to create an account". The base excludes people who were "just browsing", and the page states no year. Baymard Institute, https://baymard.com/lists/cart-abandonment-rate (checked 2026-11-16)

## Search

- **hreflang:** "Doing so will help Google Search point users to the most appropriate version of your page by language or region." On x-default: "The reserved x-default value is used when no other language/region matches the user's browser setting." https://developers.google.com/search/docs/specialty/international/localized-versions (checked 2026-11-17)
- **Meta descriptions:** "Identical or similar descriptions on every page of a site aren't helpful when individual pages appear in search results." Also: "Wherever possible, create descriptions that accurately describe the specific page." https://developers.google.com/search/docs/appearance/snippet (checked 2026-11-17)

## Structured data

- **Review snippets:** "At least one of ratingCount or reviewCount is required". Also: "If you use AggregateRating, users should be able to see that aggregate rating on the page." https://developers.google.com/search/docs/appearance/structured-data/review-snippet (checked 2026-11-16)
- **Structured data policies:** "Your structured data must be a true representation of the page content." Also: "Don't mark up content that is not visible to readers of the page." Breaking these rules "can result in a manual action". https://developers.google.com/search/docs/appearance/structured-data/sd-policies (checked 2026-11-16)

## Privacy in the EU

- **Estonia, analytics cookies without consent:** an EDPB national news item from January 2023 reports a decision of the Estonian supervisory authority (AKI), dated 25 July 2022, against Ticketer OÜ. The company had set third-party cookies without prior consent and was ordered to collect consent or remove them. https://www.edpb.europa.eu/news/national-news/2023/estonian-sa-ticketer-ou-shortcomings-privacy-policy-third-party-cookies_nb (checked 2026-11-16)

- **Netherlands, tracking cookies need consent (AP):** "Other cookies, such as tracking cookies, have consequences for your privacy. That is why you must give the website or app consent for placing these type of cookies." No valid consent: "Websites that assume your consent if you continue using the site (keep scrolling or swiping) after an information banner has been displayed." https://www.autoriteitpersoonsgegevens.nl/en/themes/internet-and-smart-devices/cookies (checked 2026-11-17; WebFetch gets 403, read with curl)
- **Netherlands, reject button on the first layer (AP, Dutch):** "Verstop de weigerknop niet: Zet de knoppen voor weigeren en accepteren op dezelfde laag." (Don't hide the reject button: put reject and accept on the same layer.) It adds that the visitor should not have to click through, scroll or look for a text link to refuse. https://www.autoriteitpersoonsgegevens.nl/themas/internet-slimme-apparaten/cookies/heldere-cookiebanners (checked 2026-11-17)

- **Netherlands, AP enforcement on cookie banners:** NOS, 15 April 2025: "De toezichthouder dreigt met boetes voor websites die hun cookiebeleid niet binnen drie maanden op orde hebben." https://nos.nl/l/2563725 (checked 2026-11-17 by the Reviewer)

## Platform evidence

- **Fastly for Magento 2, query parameters removed from the cache key:** the module's default list is in https://github.com/fastly/fastly-magento2/blob/master/etc/config.xml. In the ocusoft audit, `srsltid`, `msclkid` and `ttclid` were not on it. (checked 2026-11-16)

## Magento versions

- **Support dates (Adobe Commerce):** end of standard support for 2.4.4 was April 12, 2025; 2.4.5 August 12, 2025; 2.4.6 August 11, 2026; 2.4.7 May 31, 2027; 2.4.8 May 31, 2028; 2.4.9 (released May 12, 2026) May 31, 2029. 2.4.4–2.4.6 have a one-time security-only period until May 31, 2027 (2.4.6 until May 31, 2028). The table lists nothing older than 2.4.4. https://experienceleague.adobe.com/en/docs/commerce-operations/release/planning/lifecycle-policy (page updated 2026-09-18, checked 2026-11-19)

## Not verified

Check these before citing them:
- How far Consent Mode v2 applies to sites that use only Google Analytics: https://support.google.com/google-ads/answer/13695607
- European Accessibility Act (Directive (EU) 2019/882): applies to e-commerce services from 28 June 2025, and microenterprises providing services (fewer than 10 employees, turnover or balance sheet up to EUR 2 million) are exempt. Secondary sources agree on this (e.g. https://www.iubenda.com/en/help/179096-eaa-compliance), but on 2026-11-18 neither the EUR-Lex text (empty page) nor the Commission page confirmed the date and the exemption. Quote the directive text itself: https://eur-lex.europa.eu/eli/dir/2019/882/oj
- Google's rule on sitemap URLs that sit on another host: https://developers.google.com/search/docs/crawling-indexing/sitemaps/large-sitemaps

## Added 2026-11-17

- **Pagination canonical:** "Don't use the first page of a paginated sequence as the canonical page"; for sorted and filtered lists Google advises noindex or robots.txt. https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading (checked 2026-11-17 by the Reviewer)
- **Product snippet offers:** every offer needs a price; a price of 0 means the product is "available without payment". https://developers.google.com/search/docs/appearance/structured-data/product-snippet (checked 2026-11-17 by the Reviewer)
- **reCAPTCHA keys in Google Cloud:** "any changes to key configuration must be made through the Google Cloud console". https://docs.cloud.google.com/recaptcha/docs/migration-overview (checked 2026-11-17 by the Reviewer)
- **Checkout abandonment reasons (Baymard):** of shoppers who abandoned during checkout (excluding "just browsing"), 40% named "Extra costs too high (shipping, tax, fees)" and 12% "I couldn't see / calculate total order cost up-front"; 17% "Website had errors / crashed". https://baymard.com/lists/cart-abandonment-rate (checked 2026-11-17)
- **Zoom blocked by viewport meta (W3C ACT rule "Meta viewport allows for zoom"):** fails when `user-scalable=no` or `maximum-scale` is below 2; supports WCAG 1.4.4 Resize text. The rule itself notes most modern mobile browsers ignore the setting or offer an override, so the impact is mainly on older mobile browsers. https://www.w3.org/WAI/standards-guidelines/act/rules/b4f0c3/ (checked 2026-11-17)

## Added 2026-11-18

- **EDPB cookie banner taskforce, no reject button (report adopted 17 January 2023):** "a vast majority of authorities considered that the absence of refuse/reject/not consent options on any layer with a consent button of the cookie consent banner is not in line with the requirements for a valid consent and thus constitutes an infringement." Also: "by default, no cookies which require consent can be set without a consent". https://www.edpb.europa.eu/system/files/2023-01/edpb_20230118_report_cookie_banner_taskforce_en.pdf (checked 2026-11-18, read with pdftotext)
- **Bing and Crawl-delay (Bing Webmaster blog, 2009):** the value is "a relative amount of throttling down you want to apply to MSNBot from its default crawl rate"; "The higher the value, the more throttled down the crawl rate will be"; "We recommend against using any value higher than 10." Old post; no newer official Bing page found. https://blogs.bing.com/webmaster/2009/08/10/crawl-delay-and-the-bing-crawler-msnbot (checked 2026-11-18)
- **WCAG 2.2 SC 2.5.8 Target Size (Minimum), AA:** "The size of the target for pointer inputs is at least 24 by 24 CSS pixels, except when:" (spacing and other exceptions follow). https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html (checked 2026-11-18)
- **Canonical URLs:** if you don't specify one, "Google will identify which version of the URL is objectively the best version to show to users in Search"; a canonical merges signals such as links from duplicate pages. https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls (checked 2026-11-18)
- **Title links:** "Avoid vague descriptors like "Home" for your home page"; "It's important to have distinct text that describes the content of the page in the <title> element". https://developers.google.com/search/docs/appearance/title-link (checked 2026-11-18)
- **Hellenic DPA, cookie recommendations (press release 09/05/2022):** C4: "The user should be able, with the same number of actions (“clicks”) and from the same level, either to accept the use of trackers (those for which consent is required) or to reject it, either all or each category separately." Also: "In the event of non-compliance with the above points or other detected breaches of the existing legislation, the Authority can impose administrative penalties." https://www.dpa.gr/en/enimerwtiko/press-releases/action-hellenic-dpa-informational-websites-cookies (checked 2026-11-18)
- **Google, 5xx errors:** "Google's indexing pipeline removes from the index URLs that persistently return a server error"; already indexed URLs are "preserved in the index, but eventually dropped". https://developers.google.com/search/docs/crawling-indexing/http-network-errors (checked 2026-11-18)
- **Google, intrusive interstitials:** "Intrusive interstitials and dialogs are page elements that obstruct users' view of the content"; they make content hard to understand, "which may lead to poor search performance." For banners instead: "You can reuse these small containers for other kinds of notifications, such as newsletter sign-up prompts." The page does not mention cookie banners; it exempts "Mandatory interstitials". https://developers.google.com/search/docs/appearance/avoid-intrusive-interstitials (checked 2026-11-18)
- **Adobe KB, non-cacheable pages:** intentionally uncacheable pages are Compare Products, Cart and Checkout; if any block in a layout is uncacheable, "the entire page becomes uncacheable"; fix: "remove the attribute `cacheable="false"` and flush the layout cache", or move the block to private content. https://experienceleague.adobe.com/en/docs/commerce-knowledge-base/kb/troubleshooting/miscellaneous/slow-performance-due-to-non-cacheable-pages (checked 2026-11-18)
- **Adobe, developer mode:** "Shows custom `X-Magento-*` HTTP request and response headers"; a page that sends X-Magento-Cache-Debug or X-Magento-Tags runs in developer mode. https://experienceleague.adobe.com/en/docs/commerce-operations/configuration-guide/setup/application-modes (checked 2026-11-19)
- **PHP end of life:** PHP 7.2 EOL "30 Nov 2020", last release 7.2.34; "using older versions may expose you to security vulnerabilities and bugs that have been fixed in more recent versions of PHP." https://www.php.net/eol.php (checked 2026-11-19)
- **Magento 2.3 end of support:** "Regular support for the 2.3 release line ended on September 8, 2022." https://experienceleague.adobe.com/en/docs/commerce-operations/release/versions (checked 2026-11-19). Lifecycle policy: staying on an unsupported version "puts your store at risk of security vulnerabilities". https://experienceleague.adobe.com/en/docs/commerce-operations/release/planning/lifecycle-policy (checked 2026-11-19)
- **Magento PHP requirements (composer.json):** 2.3.4–2.3.6 "~7.1.3||~7.2.0||~7.3.0"; 2.3.7 and 2.4.0 "~7.3.0||~7.4.0" (github.com/magento/magento2, tags; checked 2026-11-18). A shop on PHP 7.2 runs Magento 2.3.6 or older.
