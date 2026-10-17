-- Day Trader AI: SurrealDB schema (SurrealDB 2.x). Namespace `daytrader`, database `courses`.
-- Loaded by app/db/load.py; re-running it is safe (DEFINE ... OVERWRITE, UPSERT by fixed ids).
-- The full-text and vector indexes live in indexes.surql and are built after the data is in (cheaper on a small instance).
-- Layout and the reasons behind it: notes/storage-surrealdb.md.

DEFINE ANALYZER OVERWRITE english TOKENIZERS blank, class FILTERS lowercase, ascii, snowball(english);

-- Courses: course:lpp, course:ziptrader, course:cryptowizard
DEFINE TABLE OVERWRITE course SCHEMAFULL;
DEFINE FIELD OVERWRITE name ON course TYPE string;
DEFINE FIELD OVERWRITE market ON course TYPE string ASSERT $value IN ["us_equities", "crypto", "mixed"];

-- Sources: one Discord post or one video. id = the source_id, e.g. source:⟨yt:A4929OT4Jls⟩
DEFINE TABLE OVERWRITE source SCHEMAFULL;
DEFINE FIELD OVERWRITE course ON source TYPE record<course>;
DEFINE FIELD OVERWRITE kind ON source TYPE string ASSERT $value IN ["discord_post", "discord_image", "youtube"];
DEFINE FIELD OVERWRITE url ON source TYPE option<string>;
DEFINE FIELD OVERWRITE server_id ON source TYPE option<string>;
DEFINE FIELD OVERWRITE channel ON source TYPE option<string>;
DEFINE FIELD OVERWRITE channel_id ON source TYPE option<string>;
DEFINE FIELD OVERWRITE message_id ON source TYPE option<string>;
DEFINE FIELD OVERWRITE posted_at ON source TYPE datetime;
DEFINE FIELD OVERWRITE author ON source TYPE option<string>;
DEFINE FIELD OVERWRITE author_role ON source TYPE option<string>;
DEFINE FIELD OVERWRITE title ON source TYPE option<string>;
DEFINE FIELD OVERWRITE live_start ON source TYPE option<datetime>;      -- video release_timestamp: wall clock of t_s = 0
DEFINE FIELD OVERWRITE duration_s ON source TYPE option<number>;
DEFINE FIELD OVERWRITE captions ON source TYPE option<string>;
DEFINE FIELD OVERWRITE stats ON source FLEXIBLE TYPE option<object>;   -- per-session counts, airtime shares, failure kinds
DEFINE INDEX OVERWRITE source_course_time ON source FIELDS course, posted_at;

-- Segments: raw caption text in 30 s windows. Private: read through fn::context only.
-- id = segment:⟨yt:<video>:<start_s>⟩
DEFINE TABLE OVERWRITE segment SCHEMAFULL;
DEFINE FIELD OVERWRITE source ON segment TYPE record<source>;
DEFINE FIELD OVERWRITE start_s ON segment TYPE number;
DEFINE FIELD OVERWRITE end_s ON segment TYPE number;
DEFINE FIELD OVERWRITE text ON segment TYPE string;
DEFINE INDEX OVERWRITE segment_at ON segment FIELDS source, start_s;

-- Tickers: ticker:TSLA, ticker:BTCUSD
DEFINE TABLE OVERWRITE ticker SCHEMAFULL;
DEFINE FIELD OVERWRITE market ON ticker TYPE option<string>;

-- Events: what we keep from a source. id = event_id, e.g. event:⟨lpp:A4929OT4Jls:003⟩
DEFINE TABLE OVERWRITE event SCHEMAFULL;
DEFINE FIELD OVERWRITE course ON event TYPE record<course>;
DEFINE FIELD OVERWRITE source ON event TYPE record<source>;
DEFINE FIELD OVERWRITE type ON event TYPE string ASSERT $value IN ["trade", "call", "setup", "rule"];
DEFINE FIELD OVERWRITE t_s ON event TYPE option<number>;                 -- seconds into the video (null for posts)
DEFINE FIELD OVERWRITE wall ON event TYPE option<datetime>;              -- market time of the event
DEFINE FIELD OVERWRITE session_date ON event TYPE option<string>;
DEFINE FIELD OVERWRITE market ON event TYPE option<string>;
DEFINE FIELD OVERWRITE ticker ON event TYPE option<string>;
DEFINE FIELD OVERWRITE ticker_said ON event TYPE option<string>;
DEFINE FIELD OVERWRITE side ON event TYPE option<string>;
DEFINE FIELD OVERWRITE action ON event TYPE option<string>;
DEFINE FIELD OVERWRITE instrument ON event TYPE option<string>;
DEFINE FIELD OVERWRITE qty ON event TYPE option<number>;
DEFINE FIELD OVERWRITE price ON event TYPE option<number>;
DEFINE FIELD OVERWRITE entry ON event TYPE option<number>;
DEFINE FIELD OVERWRITE stop ON event TYPE option<number>;
DEFINE FIELD OVERWRITE targets ON event TYPE array<number> DEFAULT [];
DEFINE FIELD OVERWRITE level ON event TYPE option<number>;
DEFINE FIELD OVERWRITE level_kind ON event TYPE option<string>;
DEFINE FIELD OVERWRITE level_ref ON event TYPE option<string>;              -- e.g. prev_low when the level is relative
DEFINE FIELD OVERWRITE watch ON event TYPE option<string>;                  -- what the poster says to watch
DEFINE FIELD OVERWRITE horizon ON event TYPE option<string>;
DEFINE FIELD OVERWRITE why ON event TYPE option<string>;                 -- paraphrase, 15 words max
DEFINE FIELD OVERWRITE rule ON event TYPE option<string>;                -- paraphrase, 15 words max
DEFINE FIELD OVERWRITE quote ON event TYPE option<string>;               -- exact source words, 12 max
DEFINE FIELD OVERWRITE checks ON event FLEXIBLE TYPE object DEFAULT {};
DEFINE FIELD OVERWRITE fail ON event TYPE array<string> DEFAULT [];
DEFINE FIELD OVERWRITE status ON event TYPE string ASSERT $value IN ["ok", "needs_review"];
DEFINE FIELD OVERWRITE model ON event TYPE option<string>;
DEFINE FIELD OVERWRITE prompt_version ON event TYPE option<string>;
DEFINE FIELD OVERWRITE embedding ON event TYPE option<array<float>>;      -- voyage-finance-2 (1024) of rule or why
DEFINE FIELD OVERWRITE extra ON event FLEXIBLE TYPE option<object>;        -- any course-specific keys (levels, links_to, setup_tags, ...)
DEFINE INDEX OVERWRITE event_lookup ON event FIELDS course, type, ticker, wall;
DEFINE INDEX OVERWRITE event_status ON event FIELDS status;

-- Graph: event -> mentions -> ticker (cross-course "who traded TSLA and why")
DEFINE TABLE OVERWRITE mentions TYPE RELATION FROM event TO ticker;
-- Later stories: the position ledger (close -> open) and rules -> strategy
DEFINE TABLE OVERWRITE closes TYPE RELATION FROM event TO event;

-- Strategies (StrategySpec, notes/strategy-pipeline.md section 2) and backtest runs
DEFINE TABLE OVERWRITE strategy SCHEMAFULL;
DEFINE FIELD OVERWRITE course ON strategy TYPE record<course>;
DEFINE FIELD OVERWRITE version ON strategy TYPE int;
DEFINE FIELD OVERWRITE parent ON strategy TYPE option<record<strategy>>;
DEFINE FIELD OVERWRITE proposer ON strategy TYPE string ASSERT $value IN ["extractor", "agent", "human"];
DEFINE FIELD OVERWRITE spec ON strategy FLEXIBLE TYPE object;
DEFINE FIELD OVERWRITE created_at ON strategy TYPE datetime DEFAULT time::now();
DEFINE TABLE OVERWRITE part_of TYPE RELATION FROM event TO strategy;

DEFINE TABLE OVERWRITE backtest_run SCHEMAFULL;
DEFINE FIELD OVERWRITE strategy ON backtest_run TYPE record<strategy>;
DEFINE FIELD OVERWRITE window ON backtest_run TYPE string;
DEFINE FIELD OVERWRITE metrics ON backtest_run FLEXIBLE TYPE object;
DEFINE FIELD OVERWRITE trial_n ON backtest_run TYPE int;
DEFINE FIELD OVERWRITE verdict ON backtest_run TYPE option<string>;
DEFINE FIELD OVERWRITE prism_trace_id ON backtest_run TYPE option<string>;
DEFINE FIELD OVERWRITE at ON backtest_run TYPE datetime DEFAULT time::now();

-- Pre-aggregated view, kept current by SurrealDB on every event write
DEFINE TABLE OVERWRITE daily_activity AS
  SELECT course, session_date, type, count() AS n FROM event GROUP BY course, session_date, type;

-- Agent tools: the agent calls these instead of writing SurrealQL. Checked events only unless asked.
DEFINE FUNCTION OVERWRITE fn::course_summary($course: string) {
  LET $c = type::thing("course", $course);
  RETURN {
    course: $course,
    sources: count(SELECT id FROM source WHERE course = $c),
    first: (SELECT VALUE posted_at FROM source WHERE course = $c ORDER BY posted_at ASC LIMIT 1)[0],
    last: (SELECT VALUE posted_at FROM source WHERE course = $c ORDER BY posted_at DESC LIMIT 1)[0],
    events: (SELECT type, status, count() AS n FROM event WHERE course = $c GROUP BY type, status),
    top_tickers: (SELECT ticker, count() AS n FROM event WHERE course = $c AND ticker != NONE AND status = "ok" GROUP BY ticker ORDER BY n DESC LIMIT 10)
  };
};

DEFINE FUNCTION OVERWRITE fn::events($course: string, $type: option<string>, $ticker: option<string>, $from: option<datetime>, $to: option<datetime>, $include_unchecked: option<bool>, $limit: option<int>) {
  LET $c = type::thing("course", $course);
  RETURN SELECT id, type, wall, ticker, side, action, qty, price, entry, stop, targets, level, level_kind, why, rule, quote, status
    FROM event
    WHERE course = $c
      AND ($type = NONE OR type = $type)
      AND ($ticker = NONE OR ticker = $ticker)
      AND ($from = NONE OR wall >= $from)
      AND ($to = NONE OR wall <= $to)
      AND ($include_unchecked = true OR status = "ok")
    ORDER BY wall ASC
    LIMIT $limit ?? 200;
};

DEFINE FUNCTION OVERWRITE fn::search_rules($q: string, $limit: option<int>) {
  RETURN SELECT id, course, rule, why, quote, wall, search::score(1) AS score
    FROM event WHERE type = "rule" AND rule @1@ $q
    ORDER BY score DESC LIMIT $limit ?? 20;
};

DEFINE FUNCTION OVERWRITE fn::similar_rules($vec: array<float>, $k: option<int>) {
  RETURN SELECT id, course, rule, why, vector::distance::knn() AS distance
    FROM event WHERE embedding <|10,100|> $vec
    ORDER BY distance ASC LIMIT $k ?? 10;
};

DEFINE FUNCTION OVERWRITE fn::ticker_activity($ticker: string) {
  LET $t = type::thing("ticker", $ticker);
  RETURN SELECT course, type, count() AS n FROM event WHERE ->mentions->ticker CONTAINS $t GROUP BY course, type;
};

-- Raw caption text around one moment, for checking a quote. Private: never sent to PRISM or the demo.
DEFINE FUNCTION OVERWRITE fn::context($source: string, $t: number, $window: option<number>) {
  LET $w = $window ?? 60;
  RETURN SELECT start_s, text FROM segment
    WHERE source = type::thing("source", $source) AND start_s >= $t - $w AND start_s <= $t + $w
    ORDER BY start_s ASC;
};
