from collections import Counter

import mtg_optimize.search as search
from mtg_optimize.card import Card, CardChoice
from mtg_optimize.search import SearchConfig, brute_force_decks, rank_decks


def test_brute_force_reports_progress():
    choices = [
        CardChoice(Card("One", type_line="spell"), min_count=0, max_count=1),
        CardChoice(Card("Two", type_line="spell"), min_count=0, max_count=1),
    ]
    config = SearchConfig(deck_size=1, brute_force_limit=3)

    calls: list[tuple[int, int]] = []

    def progress(done: int, total: int) -> None:
        calls.append((done, total))

    decks = brute_force_decks(choices, config, progress=progress)

    assert calls[0] == (0, 3)
    assert calls[-1][0] == 3
    assert len(decks) == 2  # (0,1) and (1,0) combinations within the limit


def test_rank_decks_reports_progress(monkeypatch):
    card_a = Card("A", type_line="spell")
    card_b = Card("B", type_line="spell")
    decks = [Counter({card_a: 1}), Counter({card_b: 1})]
    config = SearchConfig()

    calls: list[tuple[int, int]] = []

    def progress(done: int, total: int) -> None:
        calls.append((done, total))

    class Dummy:
        average_score = 1.0

    monkeypatch.setattr(search, "simulate_deck", lambda deck, sim: Dummy())

    summaries = rank_decks(decks, config, progress=progress)

    assert calls[0] == (0, 2)
    assert calls[-1] == (2, 2)
    assert len(summaries) == 2
