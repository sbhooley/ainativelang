# Cache Warmup Pattern

> **⚠️ DESIGN PREVIEW**: The `graph { node ... }` syntax shown in this document
> is a **design preview for AINL 2.0** and does not compile with the current
> AINL compiler (v1.3.3). The current working syntax uses single-character
> opcodes (`S`, `R`, `X`, `J`, `If`, `Set`). See `examples/hello.ainl` or
> `AGENTS.md` in the repo root for real, compilable syntax.


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

### Real AINL Syntax (v1.3.3 — this compiles)

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
