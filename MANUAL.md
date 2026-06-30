# Manual — Run the BfV scrape on your own machine (with local Claude Code)

This session runs in a locked-down cloud environment whose network policy
**blocks outbound connections to the open internet**, so the scrape cannot run
here. Run it locally instead, where your machine has normal internet access.

You can either follow the steps yourself, or **paste the "Prompt for local Claude
Code" at the bottom** into Claude Code running on your own computer and let it do
the whole thing.

---

## Prerequisites

- **Python 3.10 or higher** (`python3 --version`)
- **git**
- A normal internet connection (no corporate proxy blocking outbound HTTPS)

---

## Step-by-step

### 1. Get the repository

```bash
git clone <your-bankresearch-repo-url>
cd bankresearch
git fetch origin claude/scrapling-repo-install-lhnv14
git checkout claude/scrapling-repo-install-lhnv14
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install the browser binaries (one time)

The stealth fetcher drives a real browser, so download them once:

```bash
scrapling install
```

(This downloads Chromium + the fingerprint/stealth dependencies. ~few hundred MB.)

### 5. Confirm the target URL

Open `scrape_bfv.py` and check the `BASE_URL` near the top of the CONFIG block:

```python
BASE_URL = "https://www.bfv-ag.de/"   # <-- replace with the real BfV homepage
```

⚠️ **Confirm this is the correct Bank für Vermögen homepage before running.**
If BfV uses extra hosts (e.g. a separate academy subdomain), add them to
`ALLOWED_HOSTS`.

You can also tune:
- `MAX_PAGES` (default 400) — total page cap
- `MAX_DEPTH` (default 4) — link depth from the homepage
- `REQUEST_DELAY` (default 2.0s) — politeness delay between pages
- `HEADLESS` — set `False` to watch the browser work

### 6. Run the scrape

```bash
python scrape_bfv.py
```

It prints progress as it goes. When finished, look in the `data/` folder:

| File | What it is |
| --- | --- |
| `data/pages.jsonl` | One row per page — title, meta, headings, forms, CTAs, links |
| `data/summary.json` | Aggregate numbers (page count, landing pages, lead forms, sections) |
| `data/all_urls.txt` | Complete URL inventory (crawl + sitemap) |
| `data/REPORT.md` | Auto-generated report skeleton to flesh out |

### 7. Turn it into the presentation report

Ask local Claude Code (or do it manually) to read `data/pages.jsonl` and
`data/summary.json` and expand `data/REPORT.md` into the full competitive teardown,
cross-referencing `docs/partner-bank-vs-bfv-strategy.md`.

### 8. (Optional) Commit the results back

```bash
git add data/
git commit -m "Add BfV scrape results and report"
git push -u origin claude/scrapling-repo-install-lhnv14
```

---

## Troubleshooting

- **`ModuleNotFoundError: scrapling.fetchers`** → you skipped `pip install -r requirements.txt`.
- **Browser/Playwright errors** → run `scrapling install` (or `scrapling install --force`).
- **Site won't load / blocked** → the site has anti-bot. `SOLVE_CLOUDFLARE = True` is
  already set; try `HEADLESS = False` to watch, and increase `PAGE_TIMEOUT`.
- **Very few pages found** → the site may rely on a sitemap not at the default path,
  or load links via JavaScript only. Check `data/all_urls.txt` and consider raising
  `MAX_DEPTH`.
- **Be respectful** — keep `REQUEST_DELAY` reasonable and only scrape public pages.

---

## Prompt for local Claude Code

Copy-paste this into Claude Code on your own machine, inside the cloned repo:

> I'm in the `bankresearch` repo on branch `claude/scrapling-repo-install-lhnv14`.
> Please: (1) create and activate a Python venv, (2) `pip install -r requirements.txt`,
> (3) run `scrapling install` to get the browsers, (4) confirm `BASE_URL` in
> `scrape_bfv.py` is the correct Bank für Vermögen homepage (ask me if unsure),
> (5) run `python scrape_bfv.py`, then (6) read `data/pages.jsonl` and
> `data/summary.json` and expand `data/REPORT.md` into a polished competitive
> teardown I can present, cross-referencing `docs/partner-bank-vs-bfv-strategy.md`.
> Tell me the headline numbers (total pages, landing pages, lead forms) when done.
