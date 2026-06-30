"""Minimal Scrapling example.

Run with:  python example.py

Fetches a demo page and prints the quotes found on it. This verifies that
Scrapling and its fetcher dependencies are installed correctly.
"""

from scrapling.fetchers import Fetcher


def main() -> None:
    page = Fetcher.get("https://quotes.toscrape.com/")
    quotes = page.css(".quote .text::text").getall()

    print(f"Found {len(quotes)} quotes:\n")
    for quote in quotes:
        print(f"  - {quote}")


if __name__ == "__main__":
    main()
