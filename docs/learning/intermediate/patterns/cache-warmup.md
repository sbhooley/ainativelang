# Cache Warmup Pattern

> **ℹ️ TWO SYNTAX STYLES**: This document shows two AINL syntax styles:
> 1. **Compact syntax** (works now) — Python-like, recommended for new code.
>    See `examples/compact/` and `AGENTS.md` for the full reference.
> 2. **Graph block syntax** (`graph { node ... }`) — **DESIGN PREVIEW**, does
>    NOT compile. These blocks are labeled "Design Preview" below.
>
> Use compact syntax for real projects: `ainl validate <file> --strict`


Pre-populate cache with LLM responses to reduce costs and latency for repeated queries.

---

## Use Case

You have an LLM node that answers the same questions repeatedly:
- FAQ chatbot
- Product information lookup
- Code review suggestions for common patterns

LLM costs add up. Cache responses so subsequent identical queries hit cache instead of LLM.

---

## Implementation

### Real AINL Syntax (v1.8.0 — this compiles)

```ainl
# cached_qa.ainl — Cache LLM responses to reduce cost
# ainl validate cached_qa.ainl --strict

S app core noop

L_start:
  R core.GET ctx "question" ->question
  # Normalize key: lowercase, trim
  R core.lower question ->norm_q
  X cache_key (core.add "qa:" norm_q)

  # Check cache
  R cache.get cache_key ->cached
  If cached ->L_cached ->L_ask_llm

L_cached:
  J cached

L_ask_llm:
  R llm.query question ->answer
  # Store in cache
  R cache.set cache_key answer ->_
  J answer
```

### Design Preview Syntax (AINL 2.0 — does NOT compile yet)

```ainl
graph CachedQA {
  input: Query = { question: string }
  
  node check_cache: Cache("lookup") {
    key: "qa:{{input.question | lower | trim}}"
    ttl: 24h
  }
  
  node answer: LLM("answer-faq") {
    prompt: |
      Q: {{input.question}}
      A:
    model: openai/gpt-4o-mini
    max_tokens: 200
  }
  
  node store_cache: Cache("store") {
    key: "qa:{{input.question | lower | trim}}"
    value: answer.result
    ttl: 24h
  }
  
  node route: switch(check_cache.hit) {
    case true -> return_cached
    case false -> answer_and_store
  }
  
  node return_cached: Transform("return") {
    result: check_cache.value
  }
  
  node answer_and_store: sequence(answer, store_cache) {
    result: answer.result
  }
  
  output: route.result
}
```
