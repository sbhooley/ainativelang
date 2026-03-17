# AI Native Lang (AINL) Patterns Library (v0.9 profile, 1.0-compatible)

This file describes **named graph/label patterns** that small models can reuse instead of re‑inventing common control flows.

Each pattern is:

- **Named** (for reference in prompts and docs).
- **Shown** as a small AINL label snippet.
- **Explained** briefly in plain English.

All patterns are compatible with the v0.9 profile in `reference/AINL_V0_9_PROFILE.md`.
For canonical runtime behavior and strict literal policy, also see:

- `RUNTIME_COMPILER_CONTRACT.md`
- `CONFORMANCE.md#minimal-conformance-test-matrix-intended`

---

## 1. RetryWithBackoff

**Name**: `RetryWithBackoff`  
**Intent**: Wrap a single `R` call so that transient failures are retried with delay.

### 1.1 Shape

```text
L1:
  R http.Get "https://api.example.com/users" ->resp
  Err ->L1_retry
  J resp

L1_retry:
  Retry @n1 3 1000
  J resp
```

### 1.2 Notes

- `Retry @n1 3 1000` means: for node `n1` (the `R` call), retry up to 3 times with 1000ms backoff.
- The compiler/runtime turn this into a graph with a `Retry` node and an `err`/`retry` edge pair.
- Use canonical node-id forms (`n<number>`) for deterministic strict-mode behavior.

---

## 2. RateLimit

**Name**: `RateLimit`  
**Intent**: Enforce a simple per‑key rate limit for a label.

### 2.1 Sketch

```text
L1:
  R cache.Get "limit:users" ->count
  If count ->L1_block
  R cache.Set "limit:users" next_count 60 ->ok
  # ... main work ...
  J out

L1_block:
  # Return a friendly error or empty result
  J out
```

### 2.2 Notes

- `next_count` is usually computed in a preceding `Set` / arithmetic node; left implicit here for brevity.
- In strict mode, if `next_count` is intended as a string literal rather than a variable, quote it explicitly.

---

## 3. BatchProcess

**Name**: `BatchProcess`  
**Intent**: Read a collection, map over items, and enqueue work.

```text
Lbatch:
  R db.F Job * ->jobs
  # Pseudocode: for each job in jobs, produce job_msg
  R queue.Put "jobs" job_msg ->msg_id
  J msg_id
```

---

## 4. CacheWarm

**Name**: `CacheWarm`  
**Intent**: Periodically prefill a cache from a data source.

```text
S core cron
Cr Lwarm "0 * * * *"   # hourly

Lwarm:
  R db.F User * ->users
  R cache.Set "users:all" users 300 ->ok
  J ok
```

---

## 5. How to use patterns as a small model

When generating AINL from English:

- Match the user intent to one or more patterns (`RetryWithBackoff`, `CacheWarm`, etc.).
- Instantiate the pattern:
  - Replace adapter names/targets (e.g. `http.Get` URL).
  - Wire outputs into surrounding labels (`->resp`, `->users`).
- Rely on the compiler + graph tooling to:
  - Normalize graphs.
  - Enforce single‑exit and adapter contracts.
  - Provide debug envelopes when runs fail.

