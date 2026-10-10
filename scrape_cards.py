"""Scrape every card from https://piltoverarchive.com/cards into a JSON file.

The card library is a Next.js app: each listing page embeds the full card data
(the same data the card modal displays) in its React Server Components payload
(`self.__next_f.push([1, "..."])` script chunks). We walk every page, decode
that payload, and pull out the `variants` arrays.

Uses only the standard library. Usage:
    python scrape_cards.py [--out cards.json] [--delay 1.0]
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "https://piltoverarchive.com/cards"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', re.S)
TOTAL_PAGES_RE = re.compile(r'"totalPages":(\d+)')
DECODER = json.JSONDecoder()


def fetch(url, retries=4):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt * 2
            print(f"  fetch failed ({exc}); retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)


def rsc_payload(html):
    """Concatenate the decoded flight-data chunks embedded in the page."""
    return "".join(json.loads(m.group(1)) for m in PUSH_RE.finditer(html))


def clean(value):
    """Translate RSC value encodings ($undefined, $D<date>, $$) to plain JSON."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, str) and value.startswith("$"):
        if value == "$undefined":
            return None
        if value.startswith("$D"):
            return value[2:]
        if value.startswith("$$"):
            return value[1:]
    return value


def extract_variants(payload):
    variants = []
    for m in re.finditer(r'"variants":\[', payload):
        try:
            arr, _ = DECODER.raw_decode(payload, m.end() - 1)
        except json.JSONDecodeError:
            continue
        variants.extend(
            v for v in arr if isinstance(v, dict) and "variantNumber" in v
        )
    return [clean(v) for v in variants]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="cards.json", help="output JSON file")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds to wait between page requests")
    args = parser.parse_args()

    cards = {}
    page, total_pages = 1, None
    while total_pages is None or page <= total_pages:
        payload = rsc_payload(fetch(f"{BASE_URL}?page={page}"))
        if total_pages is None:
            m = TOTAL_PAGES_RE.search(payload)
            total_pages = int(m.group(1)) if m else 1
        found = extract_variants(payload)
        for v in found:
            cards.setdefault(v["id"], v)
        print(f"page {page}/{total_pages}: {len(found)} cards "
              f"(total {len(cards)})")
        if not found:
            break
        page += 1
        time.sleep(args.delay)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(list(cards.values()), f, ensure_ascii=False, indent=2)
    print(f"Saved {len(cards)} cards to {args.out}")


if __name__ == "__main__":
    main()
