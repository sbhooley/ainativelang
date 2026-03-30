# Cache Warmup Pattern

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
