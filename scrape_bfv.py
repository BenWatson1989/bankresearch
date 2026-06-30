"""
Competitor site scraper for Bank für Vermögen (BfV).

What it does
------------
1. Reads robots.txt + sitemap(s) to build a complete inventory of public URLs.
2. Crawls the site (same-domain, breadth-first) using Scrapling's StealthyFetcher,
   which drives a real stealth browser and can clear Cloudflare/anti-bot.
3. For every page it records the signals that matter for a competitive teardown:
   title, meta description, canonical, language, headings, word count, forms and
   their fields (lead capture!), CTA button text, internal/external link counts,
   and whether the page looks like a dedicated landing page.
4. Writes machine-readable output (JSONL + JSON) and a human-readable REPORT.md
   skeleton with the aggregate numbers (how many pages, how many landing pages,
   how many lead forms, etc.) ready to be turned into the final presentation.

Run it
------
    python scrape_bfv.py

All behaviour is controlled by the CONFIG block below. Nothing else needs editing
for a first run. See MANUAL.md for the full local setup.
"""

from __future__ import annotations

import json
import sys
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

from scrapling.fetchers import StealthyFetcher

# --------------------------------------------------------------------------- #
# CONFIG  --  edit these                                                       #
# --------------------------------------------------------------------------- #

# !!! CONFIRM THIS URL BEFORE RUNNING !!!
# Bank für Vermögen AG (BCA Group). Best-guess domain below — replace with the
# real homepage if different. Use the apex the site actually serves on.
BASE_URL = "https://www.bfv-ag.de/"

MAX_PAGES = 400          # hard cap on number of pages to crawl
MAX_DEPTH = 4            # link depth from the homepage (homepage = depth 0)
REQUEST_DELAY = 2.0      # seconds to wait between page fetches (be polite)
SOLVE_CLOUDFLARE = True  # let Scrapling clear Cloudflare Turnstile/Interstitial
HEADLESS = True          # set False locally if you want to watch the browser
PAGE_TIMEOUT = 60000     # per-page timeout in milliseconds

# Only follow links on these hosts. Defaults to the BASE_URL host (+ www variant).
# Add extra hosts here if BfV uses several (e.g. an academy subdomain).
ALLOWED_HOSTS: set[str] = set()

# Skip URLs whose path ends with these (assets, not pages).
SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp4", ".mp3", ".avi", ".mov", ".css", ".js", ".woff", ".woff2", ".ttf",
)

OUTPUT_DIR = Path("data")

# --------------------------------------------------------------------------- #
# Internals                                                                    #
# --------------------------------------------------------------------------- #


@dataclass
class PageRecord:
    url: str
    depth: int
    status: int | None = None
    title: str = ""
    meta_description: str = ""
    meta_keywords: str = ""
    canonical: str = ""
    lang: str = ""
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    word_count: int = 0
    num_forms: int = 0
    forms: list[dict] = field(default_factory=list)
    cta_texts: list[str] = field(default_factory=list)
    internal_links: int = 0
    external_links: int = 0
    images: int = 0
    is_landing_page: bool = False
    in_sitemap: bool = False
    error: str = ""


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def normalize(url: str) -> str:
    """Drop fragments and trailing-slash noise so we don't crawl dupes."""
    url, _frag = urldefrag(url)
    if url.endswith("/") and url.count("/") > 3:
        url = url.rstrip("/")
    return url


def is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc.lower() not in ALLOWED_HOSTS:
        return False
    if parsed.path.lower().endswith(SKIP_EXTENSIONS):
        return False
    return True


def setup_allowed_hosts() -> None:
    base_host = host_of(BASE_URL)
    ALLOWED_HOSTS.add(base_host)
    # Treat www / non-www as the same site.
    if base_host.startswith("www."):
        ALLOWED_HOSTS.add(base_host[4:])
    else:
        ALLOWED_HOSTS.add("www." + base_host)


def fetch(url: str):
    """Fetch one URL through the stealth browser. Returns a Response or None."""
    try:
        return StealthyFetcher.fetch(
            url,
            headless=HEADLESS,
            network_idle=True,
            solve_cloudflare=SOLVE_CLOUDFLARE,
            google_search=False,
            timeout=PAGE_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 - we want to keep crawling
        print(f"  ! fetch failed: {exc}", file=sys.stderr)
        return None


def discover_sitemap_urls() -> set[str]:
    """Pull every <loc> from robots.txt-advertised + default sitemaps."""
    found: set[str] = set()
    candidates = [
        urljoin(BASE_URL, "/sitemap.xml"),
        urljoin(BASE_URL, "/sitemap_index.xml"),
    ]

    # robots.txt may advertise extra sitemaps
    robots = fetch(urljoin(BASE_URL, "/robots.txt"))
    if robots is not None:
        for line in robots.get_all_text().splitlines():
            if line.lower().startswith("sitemap:"):
                candidates.append(line.split(":", 1)[1].strip())

    seen_sitemaps: set[str] = set()
    queue = deque(dict.fromkeys(candidates))
    while queue:
        sm = queue.popleft()
        if sm in seen_sitemaps:
            continue
        seen_sitemaps.add(sm)
        resp = fetch(sm)
        if resp is None:
            continue
        locs = resp.xpath("//*[local-name()='loc']/text()").getall()
        for loc in locs:
            loc = loc.strip()
            if loc.endswith(".xml"):
                queue.append(loc)          # nested sitemap index
            else:
                found.add(normalize(loc))
        print(f"  sitemap {sm}: {len(locs)} entries")
    return found


def extract(record: PageRecord, resp) -> set[str]:
    """Populate a PageRecord from a Response and return discovered links."""
    record.status = getattr(resp, "status", None)
    record.title = (resp.css("title::text").get() or "").strip()
    record.meta_description = (
        resp.css("meta[name='description']::attr(content)").get() or ""
    ).strip()
    record.meta_keywords = (
        resp.css("meta[name='keywords']::attr(content)").get() or ""
    ).strip()
    record.canonical = (
        resp.css("link[rel='canonical']::attr(href)").get() or ""
    ).strip()
    record.lang = (resp.css("html::attr(lang)").get() or "").strip()
    record.h1 = [t.strip() for t in resp.css("h1::text").getall() if t.strip()]
    record.h2 = [t.strip() for t in resp.css("h2::text").getall() if t.strip()]

    body_text = resp.get_all_text(ignore_tags=("script", "style"))
    record.word_count = len(body_text.split())

    # Forms (lead capture is the key competitive signal)
    forms = resp.css("form")
    record.num_forms = len(forms)
    for form in forms:
        fields = []
        for inp in form.css("input, select, textarea"):
            fields.append(
                {
                    "tag": inp.tag,
                    "type": inp.attrib.get("type", ""),
                    "name": inp.attrib.get("name", ""),
                    "placeholder": inp.attrib.get("placeholder", ""),
                }
            )
        record.forms.append(
            {
                "action": form.attrib.get("action", ""),
                "method": form.attrib.get("method", ""),
                "fields": fields,
            }
        )

    # CTA-ish elements: buttons + anchors that look like calls to action
    ctas = []
    for el in resp.css("button, a.btn, a.button, .cta, [role='button']"):
        txt = el.get_all_text().strip()
        if txt:
            ctas.append(txt)
    record.cta_texts = ctas[:25]

    record.images = len(resp.css("img"))

    # Links
    links: set[str] = set()
    internal = external = 0
    for href in resp.css("a::attr(href)").getall():
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = normalize(urljoin(record.url, href))
        if host_of(absolute) in ALLOWED_HOSTS:
            internal += 1
            if is_allowed(absolute):
                links.add(absolute)
        else:
            external += 1
    record.internal_links = internal
    record.external_links = external

    # Heuristic: a "landing page" tends to be a focused page with a lead form,
    # strong CTAs, and a single dominant H1 message.
    record.is_landing_page = bool(
        record.num_forms >= 1 and (record.cta_texts or len(record.h1) <= 2)
    )

    return links


def crawl() -> list[PageRecord]:
    setup_allowed_hosts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Target: {BASE_URL}")
    print(f"Allowed hosts: {sorted(ALLOWED_HOSTS)}")
    print("\n[1/2] Discovering sitemap URLs ...")
    sitemap_urls = discover_sitemap_urls()
    print(f"  -> {len(sitemap_urls)} URLs found in sitemap(s)\n")

    print("[2/2] Crawling ...")
    start = normalize(BASE_URL)
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    # Seed the queue with sitemap URLs at depth 1 so we cover orphan pages too.
    for u in sorted(sitemap_urls):
        if is_allowed(u):
            queue.append((u, 1))

    seen: set[str] = set()
    records: list[PageRecord] = []
    jsonl_path = OUTPUT_DIR / "pages.jsonl"
    jsonl = jsonl_path.open("w", encoding="utf-8")

    while queue and len(records) < MAX_PAGES:
        url, depth = queue.popleft()
        if url in seen or depth > MAX_DEPTH:
            continue
        seen.add(url)

        print(f"  [{len(records) + 1}/{MAX_PAGES}] d{depth} {url}")
        record = PageRecord(url=url, depth=depth, in_sitemap=url in sitemap_urls)
        resp = fetch(url)
        if resp is None:
            record.error = "fetch_failed"
        else:
            try:
                for link in extract(record, resp):
                    if link not in seen:
                        queue.append((link, depth + 1))
            except Exception as exc:  # noqa: BLE001
                record.error = f"parse_error: {exc}"

        records.append(record)
        jsonl.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        jsonl.flush()
        time.sleep(REQUEST_DELAY)

    jsonl.close()
    write_summary(records, sitemap_urls)
    return records


def write_summary(records: list[PageRecord], sitemap_urls: set[str]) -> None:
    pages_with_forms = [r for r in records if r.num_forms > 0]
    landing_pages = [r for r in records if r.is_landing_page]
    errors = [r for r in records if r.error]

    # Group URLs by first path segment to show the site's section structure.
    sections: dict[str, int] = {}
    for r in records:
        seg = urlparse(r.url).path.strip("/").split("/")[0] or "(home)"
        sections[seg] = sections.get(seg, 0) + 1

    summary = {
        "base_url": BASE_URL,
        "pages_crawled": len(records),
        "urls_in_sitemap": len(sitemap_urls),
        "pages_with_forms": len(pages_with_forms),
        "likely_landing_pages": len(landing_pages),
        "pages_with_errors": len(errors),
        "sections": dict(sorted(sections.items(), key=lambda x: -x[1])),
        "landing_page_urls": [r.url for r in landing_pages],
        "form_page_urls": [r.url for r in pages_with_forms],
    }
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT_DIR / "all_urls.txt").write_text(
        "\n".join(sorted(set(r.url for r in records) | sitemap_urls)),
        encoding="utf-8",
    )
    _write_report_skeleton(summary, records)

    print("\n=== DONE ===")
    print(f"  Pages crawled:        {summary['pages_crawled']}")
    print(f"  URLs in sitemap:      {summary['urls_in_sitemap']}")
    print(f"  Pages with forms:     {summary['pages_with_forms']}")
    print(f"  Likely landing pages: {summary['likely_landing_pages']}")
    print(f"  Errors:               {summary['pages_with_errors']}")
    print(f"\nOutput written to: {OUTPUT_DIR.resolve()}")
    print("  - pages.jsonl   (one row per page, full detail)")
    print("  - summary.json  (aggregate numbers)")
    print("  - all_urls.txt  (complete URL inventory)")
    print("  - REPORT.md     (report skeleton to flesh out)")


def _write_report_skeleton(summary: dict, records: list[PageRecord]) -> None:
    lines = [
        "# Bank für Vermögen — Website Teardown (auto-generated draft)",
        "",
        f"Source: {summary['base_url']}",
        "",
        "## Headline numbers",
        "",
        f"- Pages crawled: **{summary['pages_crawled']}**",
        f"- URLs listed in sitemap(s): **{summary['urls_in_sitemap']}**",
        f"- Pages containing a form (lead capture): **{summary['pages_with_forms']}**",
        f"- Likely dedicated landing pages: **{summary['likely_landing_pages']}**",
        "",
        "## Site structure (pages per top-level section)",
        "",
        "| Section | Pages |",
        "| --- | --- |",
    ]
    for section, count in summary["sections"].items():
        lines.append(f"| `{section}` | {count} |")
    lines += [
        "",
        "## Likely landing pages",
        "",
    ]
    for url in summary["landing_page_urls"]:
        lines.append(f"- {url}")
    lines += [
        "",
        "## Pages with forms",
        "",
    ]
    for url in summary["form_page_urls"]:
        lines.append(f"- {url}")
    lines += [
        "",
        "## Notes for the final report",
        "",
        "- [ ] Review `data/pages.jsonl` for titles, meta descriptions and CTAs.",
        "- [ ] Map their advisor journey from the section structure above.",
        "- [ ] Compare landing-page count and messaging vs. Partner Bank.",
        "",
    ]
    (OUTPUT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    crawl()
