# Product

<!-- impeccable:product-schema 1 -->
<!-- Written 2026-10-17 from the session brief, not from an interview. Facts marked (inferred) need Luis's confirmation. -->

## Platform

web (one responsive page for phone and desktop; not a native app)

## Stack

Mocks: single-file static HTML/CSS/JS that works offline. App: Python (`app/`). (inferred: the production web stack is not decided yet)

## Users

1. People who paid for day-trading courses (ZipTrader, Learn Plan Profit, Crypto Wizard) and want to know if the strategies actually worked. Luis is the first one.
2. Hackathon judges at MONEY TALKS 2 seeing a live demo cold, with no walkthrough. They span AI, fintech, investing and banking.
3. (inferred) A non-trader: plain language over trading jargon.

## Product Purpose

Day Trader AI answers "did this course's strategy actually work?" It reads a course's content (Discord posts, YouTube lesson transcripts), pulls out its trading rules with citations, backtests them on historical data, then lets an AI agent propose a better version and re-backtests it. Success: a user sees the verdict for a course in seconds and can open the proof behind it.

## Positioning

It audits the courses, not the market. Every rule cites the lesson it came from. The model proposes changes; code backtests and decides. PRISM by Block Convey traces and scores every version, so each improvement has evidence.

## Track and story

Money Intelligence (decided 2026-10-17; see AGENTS.md). The demo is the failure, the fix, and the score that proves it, through three PRISM proofs: Knowledge Base (rules from the course notes), Root Cause (a cluster of failed runs and why), Evaluator (our judge scoring v1 vs v2 on the same inputs).

## Constraints

1. Sample data only for now, labelled as sample wherever a number appears.
2. Course content is copyrighted: show extracted rules and short quoted citations only, never transcripts or screenshots.
2. Fake money only; no personal financial details; no investment advice.
3. Required sponsors visible in the product: PRISM (traces, scores) and Nicrron (model gateway).
4. Fewest words on screen, one idea per screen, big answer first, details on demand.
5. Flag what it doesn't know (judging: trust and explainability).

## Terminology

1. "Course" = one paid program. "Rules" = the course's trading rules, each with a citation.
2. "Better version" = the agent's proposed tweak of the rules, re-backtested.
3. Avoid: "baseline", "in-sample", "drawdown" on first view; explain on demand.
