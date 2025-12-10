# MTG Optimize

A small toolkit that can brute-force and simulate Magic: The Gathering decklists. It focuses on Pauper-style early game testing (first ~6 turns) and automatically experiments with land mixes.

## Features
- Define a pool of candidate cards and allowed counts.
- Brute-force valid decklists (bounded by a configurable limit) to explore land ratios and spell suites, with optional guardrails for land and creature counts.
- Monte Carlo draw simulations of the first N turns, scoring decks by spells cast, mana spent, board pressure (power), interaction (removal/counters), card draw, land drops, and color screw frequency.
- CLI to rank the best-performing decks.
- Import MTGO/Arena-style text decklists and auto-fill card details using the public Scryfall API.

## How it works (and what to expect)
The tool takes a **pool** of possible cards and explores every allowed count for each one to build 60-card decks. It respects Magic's "four-of" limit automatically—spell entries default to `max: 4`, while lands can go higher if you specify a bigger `max`.

For each legal combination (bounded by a safety cap), the simulator shuffles, draws, and plays out the first few turns of many games to estimate how smoothly the deck runs. Higher scores reward casting spells and spending mana early; missing land drops or getting color-screwed lowers the score. The CLI prints the top-performing decks with average metrics so you can see how the mix of lands and spells affected consistency.

### What the outputs look like
Running the CLI prints a numbered list of the best decks. Each entry shows:

- **Avg score**: Composite fitness value (higher is better).
- **Spells cast / Mana spent**: How much action the deck produced in early turns.
- **Board pressure / Interaction / Card draw / Finishers**: High-impact plays beyond just curving out.
- **Color screw turns / Missed land drops**: Lower is better; indicates stumbling.
- **Deck breakdown**: The exact counts chosen for each candidate card.
- Progress messages are printed to stderr during long runs to show deck-search and simulation completion percentages.

### How scoring works
Each simulated game computes a composite score designed to reward proactive starts while penalizing stumbles:

- **Proactive play**: Casting spells and spending mana early are the backbone of the score.
- **Board impact**: Creatures add their power, toughness, and any user-provided impact score to sustained pressure on the battlefield.
- **Spell impact**: Non-creature spells add their impact scores immediately when cast so utility cards can outweigh raw stats.
- **Interaction & resilience**: Removal, counterspells, and card draw tagged in the card pool add extra weight toward the total.
- **Finishers**: Cards tagged as finishers provide a further bump.
- **Penalties**: Missing land drops or failing to cast spells because of color issues subtract from the score.

Average metrics are reported over all simulated games so you can see how the scoring components contributed to a deck's placement.

## Quick start: explore a pool of options
1. Create a JSON config similar to `example_config.json` where each card describes the **allowed range** of copies to try:
   - `deck_size`: Target deck size (60 by default).
- `brute_force_limit`: Optional maximum number of combinations to examine before stopping. If omitted, the CLI will estimate the full search space quickly (capped for very large pools) and then let you choose how many decks to simulate (defaulting to 5,000 or the full count if smaller).
- `deck_rules`: Optional land/creature guardrails, e.g. `{ "min_lands": 16, "max_lands": 26, "min_creatures": 12, "max_creatures": 30 }`. These rules can also live in a standalone JSON file passed to `--rules` when importing a decklist.
   - `games` / `turns`: How many simulations to run per deck and how many turns to play out.
- `cards`: Candidate cards with `name`, `type` (`"land"`, `"creature"`, or any spell type string), `mana_cost`, `colors`, `min`/`max` copies, and optional `power`, `toughness`, and `tags` (e.g., `"removal"`, `"counter"`, `"card_draw"`, `"finisher"`) to weight advanced gameplay metrics. Non-land cards should keep `max` at 4 to follow format rules; raise land `max` as needed to let the search engine try many mana bases.
2. Run the CLI (from the repository root):
   ```bash
   PYTHONPATH=src python -m mtg_optimize.cli --config example_config.json --top 3
   ```
3. Read the printed deck summaries and pick the mix you want. If you hit the brute-force cap with fewer than `deck_size` cards, tighten ranges or reduce the card pool.

### Importing decklists as a pool or fixed deck

Point the CLI at a text decklist exported by MTGO/Arena (lines like `4 Lightning Bolt`) **or** a simple list of card names (one per line). The tool will fetch mana costs, colors, and types from Scryfall automatically and, by default, treat the list as your **pool** of candidates:

```bash
PYTHONPATH=src python -m mtg_optimize.cli --decklist my_pool.txt --games 200 --turns 6
```

In pool mode, each non-basic card (including non-basic lands) is searched from 0–4 copies by default. If you provide a number like `6 Forest`, basics are allowed to exceed four; if you omit the number entirely (`Forest`), basics can fill the whole deck size you request. When numbers are present they act as upper bounds, but the four-of cap still applies to non-basics. The search targets a 60-card deck unless you override with `--deck-size`, and examines up to 5,000 combinations unless you set `--brute-limit`.

To enforce deck-shape requirements while exploring a decklist pool, create a small JSON file such as:

```json
{ "min_lands": 16, "max_lands": 26, "min_creatures": 12, "max_creatures": 30 }
```

This repository includes a starter `deck_rules.json` you can edit directly and pass to the CLI. Update the numbers to match the constraints you want, then run with `--rules deck_rules.json` (or another path) so only decks within those bounds are generated. If you skip `--rules` but keep a `deck_rules.json` in your working directory, it will be applied automatically so searches still respect your land and creature minimums/maximums.

If you want to simulate an exact imported list instead of exploring combinations, add `--fixed-deck` (and optionally `--deck-size` to match sideboarded counts). This pins every card to the count written and reduces the search to a single simulation run; counts are required in this mode so the CLI knows how many copies to fix:

```bash
PYTHONPATH=src python -m mtg_optimize.cli --decklist my_deck.txt --fixed-deck --games 200 --turns 6
```

## Notes
- Colors are written using single-letter MTG symbols (`U`, `G`, `R`, `B`, `W`).
- The simulator greedily casts the most expensive affordable spells each turn and plays one land per turn if available.
- To experiment with only land distributions, keep spells fixed and widen the `min`/`max` range on land entries.
