# Riftbound Cards Crawler

Scrapes every card from the [Piltover Archive card library](https://piltoverarchive.com/cards)
into a JSON file, and downloads every card image.

Each listing page embeds the full card data (the same data the card modal shows) in its
Next.js payload, so the scraper walks every page (`/cards?page=N`) and extracts it. No
browser or third-party packages needed.

## Usage

Requires Python 3.8+.

```
python scrape_cards.py --out cards.json --delay 1.0
```

- `--out`: output file (default `cards.json`)
- `--images-dir`: folder for card images (default `images`)
- `--no-images`: skip downloading images
- `--workers`: parallel image downloads (default `8`)
- `--delay`: seconds between page requests (default `1.0`)

Images already in the folder are skipped, so re-runs only fetch new cards. If some
downloads fail, the script exits with an error; run it again to retry them.

## Output

`cards.json` is a list of printings (variants). Each entry includes:

- **Printing:** `variantNumber`, `rarity`, `variantType`, `artist`, `flavorText`, `imageUrl`,
  `foilMode`, `releaseDate`
- **Market:** `cardmarketId`, `tcgplayerId`, `cardmarketPrice`, `tcgplayerPrice`
- **`set`:** `name`, `prefix`, `releaseDate`
- **`card`:** `name`, `type`, `description`, `energy`, `might`, `power`, `tags`, `colors`,
  `banEffectiveDate`, and more
- **`localImage`:** path to the downloaded image, e.g. `images/OGN-001.webp`

Images are named after the collector number. Characters Windows doesn't allow in file
names become `_` (so `OGN-299*` is saved as `OGN-299_.webp`). The extension matches the
real file type, since the CDN serves a few PNGs under `.webp` URLs.
