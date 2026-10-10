# Riftbound Cards Crawler

Scrapes every card from the [Piltover Archive card library](https://piltoverarchive.com/cards)
into a JSON file.

Each listing page embeds the full card data (the same data the card modal shows) in its
Next.js payload, so the scraper walks every page (`/cards?page=N`) and extracts it. No
browser or third-party packages needed.

## Usage

Requires Python 3.8+.

```
python scrape_cards.py --out cards.json --delay 1.0
```

- `--out`: output file (default `cards.json`)
- `--delay`: seconds between page requests (default `1.0`)

## Output

`cards.json` is a list of printings (variants). Each entry includes:

- **Printing:** `variantNumber`, `rarity`, `variantType`, `artist`, `flavorText`, `imageUrl`,
  `foilMode`, `releaseDate`
- **Market:** `cardmarketId`, `tcgplayerId`, `cardmarketPrice`, `tcgplayerPrice`
- **`set`:** `name`, `prefix`, `releaseDate`
- **`card`:** `name`, `type`, `description`, `energy`, `might`, `power`, `tags`, `colors`,
  `banEffectiveDate`, and more
