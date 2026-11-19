---
name: site-audit
description: Presales website audit for the sales team. Finds the most significant performance, bug, UI/UX, accessibility, technical-SEO and missing-feature issues on a public site, backs each with proof, and delivers a short report as a Google Doc. Use whenever the user gives a domain or URL to audit or review for sales, mentions a sales or presales audit, or asks what is wrong with a prospect's website.
effort: xhigh
---

# Site audit for sales

The sales team brings this report to calls with the site's owner, a **prospect**, who usually knows their own niche better than we do. Each finding has to hold up in front of them: a specific page, visible **proof**, a business reason to care and a fix an expert would recommend today. A finding without proof stays out of the report, and so does advice the prospect could dismiss as generic, outdated or wrong for their business.

**Input:** a domain or URL, optionally with pages or areas to focus on.
**Output:** a Google Doc in English with up to 15 strong findings and a short "Also worth mentioning" list, plus a status line for the team's tracking sheet.

## Roles

Every call re-sends the whole context, so what a session costs is its number of calls times its context size. That is why the browser work runs in short subagents, each with a small context of its own, and why the main session makes few calls.

- **You, the main session:** run the scripts, start the subagents, judge and select the findings, check every proof, write `findings.json`, build the report, get the user's approval and upload it.
- **Walker** (`site-audit-walker`): walks one part of the site on desktop and mobile and appends raw observations to `walk.md`. Three Walkers run one after another, one per part.
- **Prover** (`site-audit-prover`): confirms each chosen finding in the browser and saves its proof screenshot.
- **Reviewer** (`site-audit-reviewer`, Opus at max effort, no browser): the last filter. It drops the findings a prospect's developer would dismiss in one sentence and moves small ones to `minor`, so the user never reads them. It does not rewrite. Its context is small, so the high effort costs little.

Their definitions are in the plugin's `agents/` folder, two levels above this skill (`<skill>/../../agents/`). A definition sets the model, the effort, a turn limit and the instructions, so your prompt carries only the details of this run. Use the agent type exactly as the Agent tool lists it: installed as a plugin, the types carry the plugin's prefix (`site-audit:site-audit-walker`); linked locally, they do not (`site-audit-walker`).

If no such type is listed, use `subagent_type: "general-purpose"` with the definition's model (`sonnet` for the Walker and the Prover, `opus` for the Reviewer), and begin the prompt with "Read <skill>/../../agents/<name>.md and follow it."

Run subagents one at a time, since there is one Chrome, and stay out of Chrome while one works.

## Tools

| Tool | Use it for |
|---|---|
| Claude in Chrome (`mcp__claude-in-chrome__*`) | The browser: navigate, click, hover, `read_console_messages`, `read_network_requests`, `javascript_tool`, `computer` screenshots (`save_to_disk`, `scale`) |
| `scripts/psi.py` | PageSpeed Insights: mobile and desktop, all Lighthouse categories, real-user CrUX data, and delivery basics (font and image formats, weights, compression, protocol). Each page runs 3 times and the median run is kept, since lab results vary. Accessibility, best-practices and SEO audits are detailed once per run; `--from <json> --full` re-reads a saved run with every detail. API key from `PSI_API_KEY` or `~/.config/site-audit/config.json` |
| `scripts/http_checks.py` | Host redirects, 404 status, robots.txt, whether ad and social parameters (utm, gclid, fbclid…) bypass the page cache, the `/magento_version` endpoint, and with `--pages` the cached and uncached server response of the category and product, with a cache verdict for each. Use it instead of timing pages with curl |
| `scripts/seo_crawl.py` | A sample of the sitemap (60 pages by default, `--limit` to change): broken and redirecting URLs, noindex, canonical, titles, descriptions, H1, thin and leftover pages |
| `scripts/build_report.py` | Checks `findings.json` against the acceptance criteria, builds the `.docx`, prints the Drive upload arguments |
| `references/browser.md` | The desktop and mobile tabs, platform fingerprints, tool quirks. For you, the Walkers and the Prover |
| `references/checklist.md` | What to check on each page type. For the Walkers |
| `references/judging.md` | Performance causes, measurements, "Not findings" and recommendations to avoid. For you, in Step 4 |
| `references/sources.md` | Sources already checked for `why`. For you, in Step 4 |
| `../../agents/site-audit-*.md` | The Walker, the Prover and the Reviewer |

Run the scripts by their path inside this skill's folder (`<skill>` below). Read each reference only in the step that names it.

## Custom rules

Users adapt the audit with their own rules, kept outside the plugin so that updates never overwrite them:
- `site-audit.custom.md` in the current working folder (shared by everyone who audits from it);
- `~/.config/site-audit/custom.md` (the user's own).

Read both at the start of Step 1 when they exist; `<skill>/templates/custom.md` shows their format. They take priority over this file and the references, and the working-folder file wins over the user's. The ground rules on orders, payment, passwords and forms below can never be changed by them. Write the rules in force into `notes.md` under "Custom rules", and pass each agent the ones that concern it in a `Custom rules:` line of its prompt. Give the Reviewer the paths of both files.

## Ground rules

These bind you and both subagents; the agent definitions repeat them.

- **Clean session.** Run the audit in a fresh incognito window, where the Claude extension is allowed. Incognito windows share one session until all of them are closed, so each audit starts after every incognito window was closed. The session is clean when the cart is empty, no "recently viewed" block shows, and cookie or first-visit popups appear.
- **Guest, up to the order.** Search, filter, sort, pick options and add to cart freely. In checkout, fill in what a real customer of the audited store would, so that shipping and payment methods appear: the store's main country, a valid postcode, city and street from a big city there, the name "Test Audit", the email `audit-test@example.com` (a reserved domain, so no one receives mail), and a phone number in the country's format. Never place the order: do not press the final "Place order", "Pay" or "Buy now" button, enter no card or payment details, and enter no password, since one creates an account. Leave terms and consent checkboxes unticked, since ticking one accepts terms; prove a blocked button through its `disabled` attribute. Accounts, newsletter and contact forms stay unsubmitted.
- **The audited store.** Every agent works in the one store chosen in Step 1, with its country selected wherever the site asks.
- **Proof.** Observe any behaviour (motion, timing, a broken state) twice before recording it. In `why`, quote numbers only from your own measurements or from a named source with its link (Step 4, "Sources").
- **Time-dependent UI.** For chat, opening hours and promotions, note the site's local time; a finding that depends on it gets a `caveat`, so sales re-check it before the call.
- Requests failing with `net::ERR_BLOCKED_BY_CLIENT` come from the local browser, not the site.

## Token economy

- **Few calls in the main session.** While a subagent or a script works, end your turn and wait for its notification instead of running checks of your own. A lead that needs a closer look goes into `notes.md` under "To check". If its finding is selected, the Prover checks it.
- **The ledger.** `audits/<domain>/notes.md` holds every verified fact (number, URL, device, proof file), written the moment it is verified. After a context compaction, read `notes.md` and `walk.md`, never the transcript.
- **No whole files.** Cap tool output with `head`, `sed -n` and `--items`, and read `walk.md` one part at a time.
- **findings.json once.** Write it once, then change it only with Edit, never by rewriting the whole file.
- **Cheap browser checks.** In your own browser checks, take `scale: 0.5` screenshots, and use DOM queries wherever they answer the question.
- **Short progress.** Report progress in one line per step.
- **Scratch files** go to `audits/<domain>/tmp/`.

## Workflow

### 1. Prepare

Create `audits/<domain>/` in the current directory with `psi/`, `data/`, `shots/`, `walk/`, `tmp/` and an empty `notes.md`. Read `references/browser.md`.

Open the home page in a tab of the incognito window and confirm the session is clean; if it is not, ask the user to close all incognito windows and open a new one. Look for several stores: a country or language popup on the first visit, a store switcher, or hreflang links to other domains or subdomains (.com, .co.uk, .nl). A default domain is often only a fallback for "other countries", with fewer reviews, other contacts and other settings, so auditing it produces false findings.

Then, in one question, ask the user to turn on the device emulation in a second tab (browser.md, "Desktop and mobile tabs"); when the site has several stores, ask in the same question which one to audit, listing the ones you found. Check the width of both tabs, and open the chosen store in both, with its country picked in the popup.

If the site does not load for a customer (DNS failure, 5xx, endless bot challenge, password page, geo-block), retry once. Then stop and report `Status: Cannot audit · Reason: <what happened>` with the status code or a screenshot.

Identify the platform and theme (browser.md, "Platform fingerprints"). Write it into `notes.md` together with the chosen store (domain and country), both tab ids and the site's local time. From here on, `<domain>` means the chosen store's domain, and the scripts and agents use it.

**Done when** the chosen store's home page renders in a clean incognito session in both tabs, and `notes.md` holds the store, the platform, the tab ids and the local time; or the site is reported as unauditable with a reason.

### 2. Measure

Pick three URLs: the home page, a category with many products, a product page. Start all three scripts in the background, then end your turn:

    python3 <skill>/scripts/psi.py <home> <category> <product> --out audits/<domain>/psi
    python3 <skill>/scripts/http_checks.py <domain> --pages <category> <product> --out audits/<domain>/data
    python3 <skill>/scripts/seo_crawl.py <domain> --out audits/<domain>/data

As each script finishes, read its summary in parts and copy the facts worth keeping into `notes.md`. Start the first Walker (Step 3) once `psi.py` and `http_checks.py` have finished, so that their leads go into its prompt.

Mobile results matter most. Treat each number as a lead: a poor LCP becomes a finding once you can name the element and the cause (a 900 KB hero image, a render-blocking third-party script). When field data (CrUX) exists, quote it next to the lab value: it is what real customers experience.

**Done when** all three scripts have finished (or their failure is recorded) and their key facts are in `notes.md`.

### 3. Walk (three Walkers)

Walk the site in three parts, one Walker each, one after another:

1. Home, header and menu, footer and links
2. Search and category
3. Product, cart, checkout up to the order (with test data), 404, account and contact pages (look only)

Each part covers desktop and mobile. Start each Walker with `subagent_type: "site-audit-walker"` and a prompt in this shape:

    Skill folder: <skill>
    Audit folder: <absolute path of audits/<domain>>
    Site: <domain>: <what it sells, the platform, anything a guest sees differently, such as hidden prices>
    Store: <the chosen store and the country to pick wherever the site asks>
    Part <N> of 3: <its page types>
    Tabs: desktop <id>, mobile <id> (<DevTools emulation of a named phone, or the frame from browser.md>)
    Pages: <the URLs for this part>
    Search terms (part 2): <in the store's own language and script, taken from its category names and product titles: a product type it sells, a customer's word for a need it serves, a common misspelling in that language>
    Leads: <facts from the scripts about these pages, such as the LCP element and LCP note on mobile, console errors, layout-shift culprits, a slow page>
    Site time zone: <zone>
    Custom rules: <the custom rules about walking and checks, or "none">

When a Walker returns, read only its part of `walk.md` (`sed -n` from its heading), then start the next part. A Walker that stopped at its turn limit leaves its part unfinished. Either continue it once with SendMessage, or add what is left to the next part's prompt.

**Done when** `walk.md` holds all three parts, each with entries for its page types on desktop and mobile.

### 4. Select the findings

Read `references/judging.md` and `references/sources.md`. Then, from `notes.md`, `walk.md` and the script summaries, pick **up to 15** findings with the most impact on sales, conversion, speed, search visibility or trust. The strongest are problems a prospect can see for themselves in ten seconds, so sales can show them live, and measured problems with a named cause. A generic or unconfirmed item never fills a slot: when the site is genuinely clean, deliver fewer and say why in `summary`. Four or five findings is a guide, not a minimum; never invent one to reach it.

**Never pad the list.** An item that is real but too small for a finding of its own goes to `minor`: one or two sentences each, up to eight. UX and UI items need a screenshot there too, so give each one to the Prover in Step 5. Give each main finding an `impact` of High, Medium or Low for the overview table: High costs sales or rankings now, Medium is clear friction, Low is worth fixing but not urgent.

- **One root cause per finding.** Observations that share one fix become one finding; different fixes make separate findings, so a recommendation listing unrelated fixes is several findings.
- **Performance** usually yields 3–4 findings, one per cause, each with its own measurement (judging.md, "Performance causes").
- **A test artifact is not a finding.** For each candidate ask: would a real customer of this store, who did everything right, run into it? A problem that may come from how we tested is not a finding until the Prover confirms it under real conditions: the wrong store or country, a skipped field, a missing postcode, one scroll position, one moment in time. Give it a `verify:` note naming the condition.
- **Normal platform behaviour is not a finding.** Check each candidate against "Not findings" in judging.md. A prospect's developer will dismiss these, and with them the rest of the report.
- **A business decision is not a defect.** Account-only checkout, prices only for logged-in customers, a minimum order or limited shipping regions are usually deliberate. Raise one only as a suggestion: name the likely reason, back the case with a statistic from a cited source, and place it last.
- **The customer's journey carries the finding:** what a shopper does and sees ("Proceed to Checkout" opens a sign-in popup). Typed URLs, curl and page config explain the cause; they belong in `evidence`.
- **Advice an expert would give today.** Check each recommendation against "Recommendations to avoid" in judging.md, and leave out any technique you are not sure is still current.
- **Fixes that scale.** When the fix means manual work across many items (product descriptions, alt texts, meta tags, translations), say how to do it at scale, such as AI-written drafts from the product data with a human review.
- **Features** need a reason on this site: competitors or marketplaces offer it, reviews or customer questions ask for it, or the catalogue clearly calls for it. Two at most.
- **Sources.** When `references/sources.md` covers a claim, quote it from there. Otherwise find a source with WebSearch, confirm the wording with WebFetch on the page itself, and add it to sources.md with the date.

Order the list: what is broken or measurably slow first, then UX and UI friction, then SEO, accessibility and operations, with suggestions and features last; by impact within each group. Open with a finding the prospect cannot argue with.

Write the findings into `audits/<domain>/findings.json` (format below) with one Write, leaving `screenshots` empty; from now on, change the file only with Edit. A finding built on a `check:` line, or on something seen only once, gets a `verify:` note in the Prover's list.

The list is now frozen: a new lead goes to `notes.md` under "Later" and stays out of this report.

**Done when** `findings.json` holds up to 15 findings in that order (fewer than 10 with the reason in `summary`), each with its `impact`, page or scenario, observation, effect, fix and any measurement, steps or error, and the smaller items are in `minor`.

### 5. Proof (Prover)

Start the Prover with `subagent_type: "site-audit-prover"` and a prompt in this shape:

    Skill folder: <skill>
    Audit folder: <absolute path of audits/<domain>>
    Store: <the chosen store and its country>
    Custom rules: <the custom rules about proof, or "none">
    Tabs: desktop <id>, mobile <id> (<how the mobile tab works>)
    Findings, one per line:
    <NN> — <title> — <URL> — <desktop|mobile> — show: <the state that must be on screen> — highlight: <element or CSS selector> — verify: <what to confirm first, when needed>
    Minor items to shoot, one per line (UX and UI only; omit the block when there are none):
    m<N> — <text> — <URL> — <desktop|mobile> — show: <state> — highlight: <element>

When it returns, open every screenshot: the problem must be visible and match the finding.
- **Failed shots:** send them back to the Prover once more with SendMessage, then drop what still fails.
- **Not reproduced:** a finding the Prover could not reproduce leaves the report, unless a measurement or the exact error text proves it.

Add the files to `screenshots` in `findings.json`, and each minor item's file to its `screenshot`. A UX or UI minor item the Prover could not reproduce or shoot leaves the report.

UX and UI findings and minor items always need a screenshot; `build_report.py` refuses them without one. For performance, console and SEO findings, the measurement, the exact error text or the script output is the proof; add a screenshot when it makes the point faster.

**Done when** every finding has proof you have looked at yourself.

### 6. Build the report

    python3 <skill>/scripts/build_report.py audits/<domain>/findings.json

The script checks the findings against the team's acceptance criteria. Fix every problem it lists and run it again.

**Done when** it prints `Report:` and the upload arguments.

### 7. Senior review (Reviewer)

Start the Reviewer with `subagent_type: "site-audit-reviewer"` and this prompt:

    Skill folder: <skill>
    Audit folder: <absolute path of audits/<domain>>
    Custom rules: <the paths of the custom rule files that exist, or "none">

While it works, end your turn and wait. If it stops at its turn limit without `review.md`, ask it once with SendMessage to write `review.md` now from what it has, with a verdict for every finding. Then read `review.md`:
- Apply every `drop` and `minor` verdict to `findings.json` with Edit. A finding moved to `minor` becomes one or two sentences and keeps its first screenshot as `screenshot`.
- Apply the order, if it names a new opening finding.
- Keep the titles of the dropped findings for Step 8.

Rebuild the report.

**Done when** every verdict is applied and the report is rebuilt.

### 8. Review with the user

The Drive connector cannot change a Google Doc once it exists, so every correction happens here, on the local file.

1. Give the user the path to the `.docx` and the findings, one line each: number, category, impact, title, page. Add the `minor` items in one line each, and one line "Reviewer dropped: <titles>", so the user can bring one back.
2. Wait for their answer.
3. Apply each change they ask for to `findings.json` with Edit, rebuild, and show the list again.

A run with no one to ask stops here with `Status: Awaiting approval · Report: <local path> · Findings: <N>`.

**Done when** the user has approved the report in chat.

### 9. Upload and hand over

Once the user has approved, call the Google Drive connector's `create_file` with exactly the arguments the last build printed. The `sha256:` reference uploads the local file once the user approves the call, and Drive converts the `.docx` into a Google Doc. Then read the new doc back (`read_file_content`) and check that every finding made it.

Reply with:
- the doc as a link;
- the number of findings;
- the top three, one line each;
- the findings with a caveat, which sales re-check before the call;
- the line for the sheet: `Status: Done · Report: <link> · Findings: <N>`

**Done when** the Google Doc exists with all findings and the user has its link.

## findings.json

```json
{
  "site": "example.com",
  "date": "2026-11-16",
  "platform": "Magento 2.4 with a Luma-based theme",
  "scope": "Home, category, product, search, cart, checkout (guest), 404; desktop 1440 px and mobile 390 px",
  "tools": "PageSpeed Insights (Lighthouse 13), Chrome DevTools console and network",
  "summary": "Optional: one or two sentences naming the biggest themes.",
  "findings": [
    {
      "category": "PERFORMANCE",
      "title": "Hero banner delays the first screen on mobile",
      "impact": "High",
      "where": "https://example.com/ (mobile)",
      "observed": "The largest element is a 1.4 MB JPEG banner marked loading=lazy; LCP is 6.2 s.",
      "why": "Shoppers on phones look at an empty screen for six seconds before they see an offer, and Google rates an LCP above 4 s as poor.",
      "recommendation": "Serve the banner as responsive WebP/AVIF (about 150 KB), drop loading=lazy and add fetchpriority=high.",
      "measurement": {"metric": "LCP", "value": "6.2 s lab, 4.1 s field p75", "page": "https://example.com/", "device": "mobile", "tool": "PageSpeed Insights", "date": "2026-11-16"},
      "screenshots": ["shots/01-hero-banner.png"]
    },
    {
      "category": "BUG",
      "title": "Size filter empties the shoe category",
      "impact": "High",
      "where": "https://example.com/men/shoes (desktop and mobile)",
      "observed": "Choosing size 42 shows 'No products found' although the list showed 12 shoes in size 42.",
      "why": "Customers who filter are ready to buy; an empty result sends them to a competitor.",
      "recommendation": "Fix the filter script error below and cover combined filters with a test.",
      "steps": ["Open https://example.com/men/shoes", "Select size 42 in the Size filter", "The product grid shows 'No products found'"],
      "error": "Uncaught TypeError: Cannot read properties of undefined (reading 'items') at filters.js:118",
      "screenshots": ["shots/02-size-filter.png"]
    }
  ],
  "psi": ["psi/example-com-mobile.json", "psi/example-com-desktop.json"],
  "minor": [
    {"category": "SEO", "text": "Category pages share one meta description; unique ones written from the category data would improve click-through."}
  ]
}
```

Rules the script enforces:
- `category` is one of PERFORMANCE, BUG, UX, UI, ACCESSIBILITY, SEO, FEATURE, DEVOPS.
- Every finding has `category`, `title`, `impact` (High, Medium or Low), `where`, `observed`, `why`, `recommendation` and at least one proof field: `screenshots`, `measurement`, `steps`, `error` or `evidence` (a list of extra proof lines, such as a request URL with its status code).
- PERFORMANCE findings carry a `measurement` with `metric`, `value`, `page`, `device` and `tool`.
- BUG findings carry `steps` to reproduce or the exact `error` text.
- `psi` (top level): the saved `psi.py` JSON files of the three pages, home, category and product, as paths relative to the audit folder (`psi/<page>-mobile.json`, `psi/<page>-desktop.json`). The report ends with a "Performance data" section built from them: real-user Core Web Vitals and the lab results, with links to run PageSpeed Insights again. Quote performance numbers in findings from these same files, so the findings and the table agree.
- UX and UI findings carry at least one screenshot.
- `minor` (optional, top level): up to 8 items, each `{"category", "text"}` with the same categories and one or two sentences of text, plus `"screenshot": "shots/m<N>-<name>.png"`, required for UX and UI items and shown smaller under the item. The report shows them after the findings under "Also worth mentioning".
- `caveat` (optional): for a finding that depends on the time of day or a campaign, worded so the prospect can read it too, such as "Seen at 03:20 site time; during business hours the bar may not show." The report shows it as a note.

Writing each finding, for a salesperson who reads it once, quickly, before a call. Short and plain beats complete: say the point once, with its strongest number, and stop.
- `title`: the problem in under 10 plain words.
- `observed`: two or three sentences, about 350 characters: what a shopper sees or what was measured, the key number, and the threshold it breaks. Explain a niche term once, briefly ("blepharitis, the eyelid condition the shop's lid scrubs treat").
- `why`: one or two sentences: one effect on sales, rankings, support load or trust.
- `recommendation`: one or two sentences, about 300 characters: the main fix, named concretely, and how to do it at scale when it touches many items. Name at most three actions; the prospect's developers work out the rest.
- **Where the rest goes:** the source, percentile, device, connection and date go in `measurement`; extra proof lines (URLs, status codes, second measurements) in `evidence`. A limitation that changes the conclusion goes in `caveat`; one that does not is left out.
- **Not this:** chains of brackets, hedges ("which suggests", "it seems"), secondary metrics next to the main one, the same fact in `observed` and `why`, and lists of every possible cause.

Example: "Real Chrome users on phones wait 3.1 s or more for the first byte on one page view in four; Google rates over 1.8 s as poor. In our test an uncached product page took 4.5 s, a cached category 0.25 s." (`observed`) and "Find which visits miss the full-page cache, usually ad links with gclid or fbclid and cache clears after stock imports, then profile an uncached product page for slow modules." (`recommendation`).

`build_report.py` warns about fields over these lengths; shorten each one it names.
