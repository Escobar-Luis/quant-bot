-- Heavy indexes, built after the bulk load (app/db/load.py applies this file last).
-- Building once over loaded rows is far cheaper on a 0.25 vCPU instance than updating them on every insert.
-- No full-text index on caption segments: it took 582 s of a 590 s load and no agent function uses it
-- (captions are read by time window through fn::context, which uses segment_at).
DEFINE INDEX OVERWRITE event_rule_text ON event FIELDS rule SEARCH ANALYZER english BM25;
DEFINE INDEX OVERWRITE event_vec ON event FIELDS embedding HNSW DIMENSION 1024 DIST COSINE;
