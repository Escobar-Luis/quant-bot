# Learn Plan Profit: exits from his Discord chat (spec-audit story 18, CAP-13, 2026-10-20)

Raw posts (gitignored): `data/lpp/discord/main_chat_close_posts_2026-10-20.jsonl` (21 posts). This note keeps counts and quotes of 12 words or fewer only (AGENTS.md shared rule 5). "The host" is the course's host; no other member is named.

## For Luis

**What we found**
1. 43 overnight trades re-checked.
2. 29 have a stated exit.
3. 14 exits were assumed.
4. Chat closes 1 of 14.
5. He closes every day.

**What changed**
1. Rule 13 is LPP's headline.
2. Rule 11 kept as alternative.

## 1. Method

1. Source: LPP's Discord server, channel `#main-chat`, window 2024-08-15 to 2025-09-12 (the results window).
2. Read-only, through Luis's own Chrome session, by the orchestrator: Discord's search box, filtered to the host's own posts in `#main-chat`. Nothing was posted, reacted to or bulk-read. The host has 3,088 posts in that channel; they were **not** read in bulk, only targeted searches.
3. Searches: (a) close words ("close", "closed", "closing") from the host; (b) for each overnight trade with an assumed exit, its ticker within the days it was held.
4. Starting set: the 43 as-taught overnight LPP v1 trades (rule 11's stitched swing trades). Of those, 29 have an exit he stated on a later stream; 14 have an assumed exit (rule 11: 5 sessions).
5. Every matching post was saved with its time (UTC) and channel to the gitignored file above. Times below are ET.

## 2. Counts

| Of the 14 assumed exits | Trades |
|---|---|
| A chat post closes it | 1 (SOUN short, entered 2025-01-24) |
| Indirect hint only | 1 (COIN short, entered 2025-06-24) |
| No post about the ticker while held | 12 |

The 14 assumed exits (rule 11's stitched swing trades with no stated close, LPP v1, 5 min; ids as in `results/lpp/v1.json`'s `as_taught_stitched` ledger):

| Trade id | Ticker | Side | First leg (ET date) | Chat |
|---|---|---|---|---|
| lpp-2024-10-22-009 | NVDA | short | 2024-10-22 | none |
| lpp-2024-10-24-000 | TSLA | short | 2024-10-24 | none |
| lpp-2024-11-13-005 | TSLA | long | 2024-11-13 | none |
| lpp-2024-11-15-001 | TSLA | short | 2024-11-15 | none |
| lpp-2024-11-26-003 | MSTR | short | 2024-11-26 | none |
| lpp-2024-12-16-003 | AVGO | short | 2024-12-16 | none |
| lpp-2024-12-17-006 | TSLA | short | 2024-12-17 | none |
| lpp-2024-12-23-005 | MSTR | short | 2024-12-23 | none |
| lpp-2025-01-14-003 | SOUN | short | 2025-01-14 | none |
| lpp-2025-01-24-001 | SOUN | short | 2025-01-24 | close, 2025-01-29 |
| lpp-2025-06-20-016 | HIMS | short | 2025-06-20 | none |
| lpp-2025-06-24-007 | COIN | short | 2025-06-24 | hint, 2025-06-25 |
| lpp-2025-07-14-005 | SOFI | short | 2025-07-14 | none |
| lpp-2025-08-26-000 | PLTR | short | 2025-08-26 | none |

1. **SOUN short:** "let me close out my soun short" (2025-01-29, 09:56 ET).
2. **COIN short:** the next day he "will consider opening one on coin again" (2025-06-25, 16:00 ET), which implies it was already closed, without saying when.
3. Story 17 (PR #65, merged) found 0 stated holds among the same 43 overnight trades in the streams.

## 3. His stated policy

1. "I have closed my mstr short as I do every day!" (2025-02-03, 19:41 ET).
2. "I will close by end of day and re open premarket" (2025-05-28, 18:25 ET).
3. He trades and closes after the stream ends (about 10:30 ET), often in the afternoon: "closing cvna long" (2025-02-19, 16:29 ET); "Coin short closed" (2025-02-13, 16:37 ET).
4. Sometimes in extended hours: "posted it for everyone to be aware that overnight hours was open" (2025-06-20); "Jut wanted to test the after market activities" (2025-09-04, 17:28 ET).

Reading: a position he still holds at a stream's end is, by his own words, closed that day unless he says otherwise. Rule 11 stitches a later stream's add, trim or close onto an earlier position, which reads the future and contradicts that policy. Rule 13 (no look-ahead: overnight only on a hold he stated before 15:55 ET) matches it, so rule 13 is now the LPP headline (contracts.md rules 11 and 13).

## 4. Gaps

1. **A channel we can't see.** On 2024-10-14 (15:06 ET) he answers that he closed earlier and "posted in" a channel that renders as unknown to Luis's account, likely one Luis no longer has access to. Its posts were not read. Story 23.
2. **Trades off the stream.** His afternoon, premarket and after-hours trades are mentioned in chat but are not in the streams, so the app never copies them. How often is not measured yet. Story 24.
3. **Exits are not yet rebuilt from chat.** The one chat close (SOUN, lpp-2025-01-24-001) and the afternoon closes are not fed to the engine yet (a follow-up once stories 23 and 24 report); under rule 13 both trades leave at 15:55 ET of their entry session (assumed), which his policy supports.
4. Search is keyword-based; a close worded differently (for example "out of", "covered") may be missed.
