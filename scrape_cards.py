"""Scrape every card from https://piltoverarchive.com/cards into a JSON file.

The card library is a Next.js app: each listing page embeds the full card data
(the same data the card modal displays) in its React Server Components payload
(`self.__next_f.push([1, "..."])` script chunks). We walk every page, decode
that payload, and pull out the `variants` arrays.

Card images are downloaded into --images-dir (skipping ones already there) and
each card gets a `localImage` field with the saved path.

Uses only the standard library. Usage:
    python scrape_cards.py [--out cards.json] [--images-dir images] [--delay 1.0]
"""

import argparse
import json
import os
import posixpath
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "https://piltoverarchive.com/cards"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', re.S)
TOTAL_PAGES_RE = re.compile(r'"totalPages":(\d+)')
DECODER = json.JSONDecoder()


def fetch(url, retries=4, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                return data if binary else data.decode("utf-8")
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


IMAGE_EXTS = (".webp", ".png", ".jpg", ".gif")


def image_basename(card, taken):
    """Build a unique, filesystem-safe name (no extension) like `OGN-001`."""
    # Some collector numbers (e.g. "OGN-299*") contain characters Windows forbids.
    base = re.sub(r'[<>:"/\\|?*]', "_", card["variantNumber"]).strip(" .")
    if base.lower() in taken:
        base = f"{base}_{card['id'][:8]}"
    taken.add(base.lower())
    return base


def sniff_ext(data, url):
    """Pick the extension from the bytes; the CDN serves some PNGs as .webp."""
    if data[8:12] == b"WEBP":
        return ".webp"
    if data[:4] == b"\x89PNG":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:3] == b"GIF":
        return ".gif"
    return posixpath.splitext(urllib.parse.urlparse(url).path)[1]


def existing_image(base_path):
    for ext in IMAGE_EXTS:
        if os.path.exists(base_path + ext):
            return base_path + ext
    return None


def download_images(cards, images_dir, workers):
    os.makedirs(images_dir, exist_ok=True)
    taken = set()
    jobs = []
    for card in cards:
        card["localImage"] = None
        if not card.get("imageUrl"):
            continue
        base_path = os.path.join(images_dir, image_basename(card, taken))
        found = existing_image(base_path)
        if found:
            card["localImage"] = found.replace(os.sep, "/")
        else:
            jobs.append((card, base_path))

    def download(job):
        card, base_path = job
        url = card["imageUrl"]
        try:
            data = fetch(url, binary=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            return f"{url}: {exc}"
        path = base_path + sniff_ext(data, url)
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
        card["localImage"] = path.replace(os.sep, "/")
        return None

    print(f"Downloading {len(jobs)} images "
          f"({len(cards) - len(jobs)} already present or missing a URL)")
    failures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, error in enumerate(pool.map(download, jobs), 1):
            if error:
                failures.append(error)
            if i % 100 == 0 or i == len(jobs):
                print(f"  images {i}/{len(jobs)}")
    for error in failures:
        print(f"  failed: {error}", file=sys.stderr)
    return len(failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="cards.json", help="output JSON file")
    parser.add_argument("--images-dir", default="images",
                        help="folder to save card images in")
    parser.add_argument("--no-images", action="store_true",
                        help="skip downloading card images")
    parser.add_argument("--workers", type=int, default=8,
                        help="parallel image downloads")
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

    cards = list(cards.values())
    failed = 0 if args.no_images else download_images(
        cards, args.images_dir, args.workers)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(cards)} cards to {args.out}")
    if failed:
        print(f"{failed} images failed; re-run to retry them", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
