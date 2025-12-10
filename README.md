# MTG Optimize

A small toolkit that can brute-force and simulate Magic: The Gathering decklists. It focuses on Pauper-style early game testing (first ~6 turns) and automatically experiments with land mixes.

## Features
- Define a pool of candidate cards and allowed counts.
- Brute-force valid decklists (bounded by a configurable limit) to explore land ratios and spell suites.
- Monte Carlo draw simulations of the first N turns, scoring decks by spells cast, mana spent, land drops, and color screw frequency.
- CLI to rank the best-performing decks.
- Import MTGO/Arena-style text decklists and auto-fill card details using the public Scryfall API.

## Quick start
1. Create a JSON config similar to `example_config.json`:
   - `deck_size`: target deck size (default 60).
   - `brute_force_limit`: cap on enumerated decks to avoid combinatorial blow-ups.
   - `games` / `turns`: simulation repetition count and turn horizon.
   - `cards`: list of candidates with `name`, `type` (land or spell), `mana_cost`, `colors`, and `min`/`max` allowed copies.
2. Run the CLI (from the repository root):
   ```bash
   PYTHONPATH=src python -m mtg_optimize.cli --config example_config.json --top 3
   ```
3. Inspect the printed deck summaries and scores to pick the best build.

### Importing existing decklists

You can skip manual JSON entry by pointing the CLI at a text decklist exported by MTGO/Arena (lines like `4 Lightning Bolt`).
The tool will fetch mana costs, colors, and types from Scryfall automatically and evaluate the exact list:

```bash
PYTHONPATH=src python -m mtg_optimize.cli --decklist my_deck.txt --games 200 --turns 6
```

## Notes
- Colors are written using single-letter MTG symbols (`U`, `G`, `R`, `B`, `W`).
- The simulator greedily casts the most expensive affordable spells each turn and plays one land per turn if available.
- To experiment with only land distributions, keep spells fixed and widen the `min`/`max` range on land entries.
