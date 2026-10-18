# Learn: the system design behind each backend call

One block per decision in `architecture.md`. Each: the choice (with an analogy), the alternatives, why here, related patterns, and scale. Cards cited are paraphrased lessons from Luis's O'Reilly System Design Masterclass knowledge base (`~/knowledge/system-design`); "not from the course" marks general knowledge.

## 1. Snapshot serving (paradigm, AD-1, AD-15)

1. **Choice:** the pipeline prints a finished newspaper each night; the API only hands out copies. Nobody edits a printed paper; tomorrow's is a new one.
2. **Alternatives:** a live database both sides write (fresh, but two writers and locks); the API computing everything on request (no staleness, but slow and costly); git as the publish channel (audited, but a human merge per night).
3. **Why here:** one writer (Luis's Mac), reads from anyone, data changes once a day, and the demo must never move.
4. **Patterns:** CQRS (separate write and read models); immutable, content-addressed storage (the id is the hash, like git); blue/green pointer flip for releases; read-heavy systems favor replicas and caches (card 18.2).
5. **Scale:** fits him today. At millions of users the snapshot goes to a CDN and every API replica binds the same id. *Interview:* "Why is a pointer flip a safe deploy?" One atomic write; rollback is flipping it back.

## 2. Files as truth, the database as a read model (AD-2)

1. **Choice:** the ledger is the paper files; the database is the index card box built from them. Lose the box, rebuild it.
2. **Alternatives:** the database as the store (rich queries, but a second writer and an outage takes verdicts down); files only (simplest, no ad-hoc queries).
3. **Why here:** verdict reads are a few known lookups; only rule search and day lookup need queries.
4. **Patterns:** model data from the queries you'll run (card 7.15); materialized views; event sourcing (the log is truth, views are derived).
5. **Scale:** at scale the read model becomes the hot path with replicas; the rule "rebuildable from the log" still holds. *Interview:* "List your top three queries and the key that serves each."

## 3. Content-addressed run cache (AD-4)

1. **Choice:** label each answer with a fingerprint of the exact question plus the data version; the same question on the same data finds the same box.
2. **Alternatives:** time-based expiry (TTL; simple, but serves stale or recomputes needlessly); no cache (runs take 0.3 s, which works today).
3. **Why here:** keys never go stale because a new snapshot is a new key, so there is no invalidation problem at all.
4. **Patterns:** cache-aside, check then load then store (card 11.7); invalidation on writes (card 16.3) avoided by immutability; LRU eviction.
5. **Scale:** small now (card: "a local dataset is usually already fast enough", 7.6). At scale, a shared cache (Redis) and request coalescing stop a stampede on a hot key. *Interview:* "What's your cache key?" Normalized query plus data version.

## 4. Synchronous runs, no queue (AD-6)

1. **Choice:** the cook makes the dish while you wait at the counter, because it takes a third of a second.
2. **Alternatives:** a job queue with workers and a status endpoint (handles long jobs and bursts, but more moving parts and a progress UI).
3. **Why here:** measured 0.27–0.56 s per run; two workers and a 429 when busy is enough.
4. **Patterns:** synchronous calls couple the caller to the callee (card 11.10); leaky bucket as a fixed-rate queue (card 5.16); backpressure.
5. **Scale:** past ~5 s per run or many users, move to a queue sized by depth. *Interview:* "Which calls must stay synchronous?" The ones the user is waiting on and that finish fast.

## 5. Offline request path (AD-5, AD-14)

1. **Choice:** the server cooks only with ingredients already in its pantry (the snapshot's bars and positions); it never runs to the store mid-order.
2. **Alternatives:** fetch bars from Alpaca on a miss (complete, but slow, key burn, and a different feed can change numbers).
3. **Why here:** one source of truth for prices means the API and the nightly numbers can't disagree.
4. **Patterns:** read-through cache (card 16.1) rejected on purpose; bulkheads (a dependency can't take the request path down); reproducible builds.
5. **Scale:** the pantry becomes object storage plus a local cache per replica. *Interview:* "How do you keep two services' numbers consistent?" Same inputs by id, same code by version.

## 6. Sign-in with Clerk, verified offline (AD-7)

1. **Choice:** a stamped ticket the door checks with a public key, without phoning the box office.
2. **Alternatives:** server sessions in our database (revocable at once, but state to store); calling Clerk on every request (always current, but adds latency and a dependency).
3. **Why here:** a stateless API is easy to run and scale; tokens expire in about a minute, so revocation lag is small.
4. **Patterns:** HTTP is stateless, so state rides in tokens (card 13.7); never trust the client for proof (card 8.12); CSRF via the `azp` check.
5. **Scale:** offline verification scales to any number of replicas with no shared state. *Interview:* "Why does statelessness make scaling easy?" Any replica can serve any request.

## 7. Picks with the identity provider (AD-8, open question 2)

1. **Choice:** keep the user's three favorite courses on their ID card (Clerk metadata), not in our own drawer.
2. **Alternatives:** browser storage (today; zero backend, one device only); our own table (queryable across users, but a database to run).
3. **Why here:** three ids, read on every visit, rarely written; no database to operate.
4. **Patterns:** a preferences store read on every request (card 9.15); different data, different stores (card 9.7); read-your-writes consistency (the token refresh rule).
5. **Scale:** at millions of users, a preferences table with a cache; provider metadata hits rate limits (10 writes per 10 s per user). *Interview:* "Preferences are read on every send but rarely change: how do you cache them?"

## 8. Traces off the request path (AD-9)

1. **Choice:** drop the receipt in an outbox and keep serving; a courier takes it to PRISM later.
2. **Alternatives:** send the trace before answering (never lost, but PRISM's latency and outages become ours); no traces (cheapest, but breaks rule 1).
3. **Why here:** a trace is evidence, not part of the answer; a bounded queue loses at most 100 on a crash, and every drop is logged.
4. **Patterns:** async log shipping (card 10.3); correlation ids (cards 10.2, 10.4: our `run_key` and `snapshot_id`); outbox pattern (not from the course).
5. **Scale:** at scale, a durable queue (Kafka) and sampling. *Interview:* "How do you trace a request that crosses an async job?" Carry the id into the job.

## 9. Rate limits and budgets in one module (AD-13)

1. **Choice:** a bucket of tokens per user that refills over time; each run takes one, and an empty bucket says "try again in N seconds".
2. **Alternatives:** fixed windows (simple, bursty at edges); a central limiter service (global, but another hop and a single point of failure).
3. **Why here:** one instance, so in-process counters are exact; one daily cap bounds compute and PRISM credits together.
4. **Patterns:** token bucket (card 5.15: tiny state, allows bursts); leaky bucket for background calls like Nicrron (card 5.16); limiter placement in each server (card 5.10).
5. **Scale:** many instances need a shared store or sticky routing. *Interview:* "With limiting in 100 servers, how do you enforce one per-user limit?" A shared counter (Redis) or consistent hashing of users.

## 10. Nightly batch on the Mac (AD-11, AD-16)

1. **Choice:** a night shift that does the whole run start to finish and only then swaps the sign on the door.
2. **Alternatives:** streaming each new post as it lands (fresh, but harder to get right); the server collecting (always on, but raw course content would leave the Mac and Discord would be read unattended).
3. **Why here:** the courses post a few times a day; the copyright and Discord rules decide where it runs.
4. **Patterns:** batch vs stream (card 10.11: "when is a batch every 5 minutes good enough?"); a pipeline of single-purpose stages (card 3.12); idempotent stages with a ledger.
5. **Scale:** a scheduler with retries and alerts (Airflow and the like) replaces launchd. *Interview:* "Design a pipeline where one event stream feeds a live alert and a nightly job" (card 18.3).

## 11. Hosting: one boring container (open question 1)

1. **Choice:** one small always-on box running one app, like a single food truck rather than a franchise.
2. **Alternatives:** serverless (free at idle, but cold starts and no disk); several regions (survives outages, but costs and replication).
3. **Why here:** one user group, a few requests a minute, bursts under a second.
4. **Patterns:** monolith first (card 11.9: the right default for small apps); failure domains (card 12.5) noted, not paid for.
5. **Scale:** split only when parts need different scaling. *Interview:* "What signals say a monolith should be split?" Team size, deploy conflicts, very different scaling needs.

Cards used: 3.12 Pipeline of single-purpose stages · 5.10 Rate limiting inside each API server · 5.15 Token bucket · 5.16 Leaky bucket · 7.6 Why cache search results · 7.15 Model data from the queries you'll run · 8.12 Server-side verification · 9.7 Different data, different stores · 9.15 User preference service · 10.2 End-to-end request tracing · 10.3 Logging must be minimally intrusive · 10.4 Correlation id · 10.11 Stream vs batch · 11.7 Cache-aside · 11.9 Monolith · 11.10 Synchronous calls · 12.5 Failure domains · 13.7 HTTP is stateless · 16.1 Read-through cache · 16.3 Stale data and invalidation · 18.2 Read-heavy vs write-heavy · 18.3 Event streaming uses.
