# Evaluator rubrics (paste into PRISM -> Evaluators -> New)

Written by `uv run python -m prism.evaluators show`. Copy each rubric exactly.

## Numbers grounded

- Type: LLM judge
- Labels: grounded, ungrounded
- Pass label: grounded (threshold 1.0)
- Score runs of: extract-lpp-v1, extract-lpp-v2
- Description: Every price, level and quantity an extracted event reports appears in the quote it cites.

Rubric:

```
You are checking one run of an extraction agent that reads a trading live-stream session.

Run output (JSON; its "events" list is what to check):
{output}

Each event may report numbers in "qty", "price" or "level", and cites the exact words it came from in "quote".
For every event that reports at least one of those numbers, check that each number appears in that same event's quote.
Captions may drop the decimal point (58.74 can appear as "5874") or say numbers as words ("a thousand" = 1000); count those as appearing.
Ignore events with no qty, price or level. Ignore the "failures" and "counts" fields.

Label "grounded" if every number of every event appears in its own quote.
Label "ungrounded" if any number does not, and name the first failing event_id and number.
```

## Verdict numbers from results

- Type: LLM judge
- Labels: grounded, ungrounded
- Pass label: grounded (threshold 1.0)
- Score runs of: daytrader-verdict-v1, daytrader-verdict-v2
- Description: Every number in the verdict is in the results it loaded; it cites a card and says Not advice.

Rubric:

```
You are checking a verdict written for someone new to trading.

Verdict:
{output}

What the run retrieved and loaded (course rules from the knowledge base, then the backtest results):
{context}

Label "grounded" only if all three hold:
1. Every number in the verdict (money, percent, trade count, minutes) appears in the backtest results above, as written or rounded.
2. The verdict cites at least one strategy card id (like LPP-ENTRY-1) that appears in the retrieved rules.
3. The verdict says "Not advice" and promises nothing: no "guaranteed", "risk-free" or "can't lose".
Otherwise label "ungrounded" and name the first number or rule that fails.
```
