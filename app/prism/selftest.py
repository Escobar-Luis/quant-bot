"""Fast checks for the code that decides (no network): uv run python -m prism.selftest"""
import json

from .common import RESULTS, clip
from .evaluators import grounded
from .verdict import check_numbers


def main():
    res = json.loads((RESULTS / "_sample.json").read_text())
    assert check_numbers("$10,000 became $10,660 (+6.6%) over 412 trades vs 18.9% [LPP-ENTRY-1]", res) == []
    assert check_numbers("$10k became about $10.7k; holding made 19%", res) == []          # rounded / $k
    assert check_numbers("$10,000 became $12,345", res) == ["$12,345"]                     # invented
    assert check_numbers("it fell 7.3% in 997 weeks", res) == ["7.3%", "997"]
    assert clip("one two three four five six seven eight nine ten eleven twelve thirteen") == \
        "one two three four five six seven eight nine ten eleven twelve …"
    assert grounded({"quote": "buying a thousand shares at 5874", "price": 58.74, "qty": None, "level": None})
    assert not grounded({"quote": "up 300 dollars on it", "price": 31.2, "qty": None, "level": None})
    assert grounded({"quote": "this is a rule", "price": None, "qty": None, "level": None})
    print("selftest OK")


if __name__ == "__main__":
    main()
