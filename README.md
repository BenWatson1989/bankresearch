# bankresearch

Web-scraping project built on [Scrapling](https://github.com/D4Vinci/Scrapling), an
adaptive web-scraping framework that handles everything from a single request to a
full-scale crawl.

## Requirements

- Python 3.10 or higher

## Installation

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

Then download the browser binaries used by the stealth/dynamic fetchers (run once):

```bash
scrapling install
```

> `requirements.txt` pins `scrapling[fetchers]`, which includes the parser engine plus
> the `Fetcher`, `StealthyFetcher`, and `DynamicFetcher` classes and the `Spider`
> crawling framework. If you only need the parser, `pip install scrapling` is enough.
> Other extras are available: `scrapling[shell]` (interactive shell + `extract` CLI),
> `scrapling[ai]` (MCP server), and `scrapling[all]`.

## Quick start

A minimal example lives in [`example.py`](example.py):

```bash
python example.py
```

```python
from scrapling.fetchers import Fetcher

page = Fetcher.get("https://quotes.toscrape.com/")
quotes = page.css(".quote .text::text").getall()
print(quotes)
```

For anti-bot protected sites (e.g. many bank portals), use the stealth fetcher:

```python
from scrapling.fetchers import StealthyFetcher

page = StealthyFetcher.fetch("https://example.com", headless=True, network_idle=True)
data = page.css(".content").getall()
```

See the [Scrapling documentation](https://scrapling.readthedocs.io/en/latest/) for the
full API, including spiders, sessions, proxy rotation, and the CLI.

## Competitor research (Bank für Vermögen)

This repo includes a competitive-research setup:

- **`scrape_bfv.py`** — a ready-to-run crawler that maps the Bank für Vermögen (BfV)
  website using the stealth fetcher: sitemap inventory, page count, landing pages,
  lead forms, CTAs, and site structure. Output lands in `data/`.
- **`MANUAL.md`** — step-by-step instructions to clone this repo and run the scrape
  on a machine with open internet access (including a copy-paste prompt for local
  Claude Code).
- **`docs/partner-bank-vs-bfv-strategy.md`** — the strategic brief: how Partner Bank
  AG should position against BfV.

> ⚠️ The scrape **cannot run inside the Claude Code web environment** — its network
> policy blocks outbound connections to the open internet. Run `scrape_bfv.py`
> locally per `MANUAL.md`. Confirm `BASE_URL` in the script is the correct BfV
> homepage before running.
