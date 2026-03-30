# Adapters Tutorial: Building a Multi-Adapter Graph

**Time**: 45 minutes  
**Prerequisites**: Complete Basics, especially "First Agent"

---

## What We'll Build

A graph that uses **multiple adapters** to:
1. Scrape a webpage (HTTP adapter)
2. Summarize content (LLM via OpenRouter)
3. Send notification (Slack HTTP adapter)
4. Store result (PostgreSQL adapter)

This demonstrates adapter diversity and proper configuration.

---

## Step 1: Project Setup

```bash
mkdir multi-adapter-demo
cd multi-adapter-demo

# Copy skeleton
cp -r ../../basics/skeleton/ .  # if exists, otherwise create fresh

# Create ainl.yaml
cat > ainl.yaml << 'EOF'
adapter: openrouter
model: openai/gpt-4o-mini
openrouter_api_key: ${OPENROUTER_API_KEY}

# Override adapter for specific nodes
adapters:
  http: builtin.http
  postgres: builtin.postgres
  slack: builtin.http
EOF
```

---

## Step 2: The Graph (multi_adapter.ainl)

```ainl
graph MultiAdapterDemo {
  input: Config = { url: string, slack_webhook: string }

  # Node 1: HTTP adapter to fetch webpage
  node fetch: HTTP("fetch") {
    method: GET
    url: input.url
    timeout: 10s
  }

  # Node 2: LLM adapter to summarize
  node summarize: LLM("summarize") {
    prompt: |
      Summarize this webpage content in 2 sentences:
      
      {{fetch.body}}
    
    max_tokens: 100
    temperature: 0.3
  }

  # Node 3: Store in PostgreSQL (SQL adapter)
  node store: SQL("store-summary") {
    query: """
      INSERT INTO scraped_pages (url, summary, fetched_at)
      VALUES ({{fetch.url}}, {{summarize.result}}, NOW())
      RETURNING id
    """
  }

  # Node 4: Send Slack notification (HTTP adapter again)
  node notify: HTTP("slack") {
    method: POST
    url: input.slack_webhook
    body: {
      text: "✅ Scraped {{fetch.url}}
Summary: {{summarize.result}}
Stored with ID: {{store.id}}"
    }
  }

  output: {
    url: fetch.url
    summary: summarize.result
    stored_id: store.id
    notified: notify.status == 200
  }
}
```

---

## Step 3: Test Run

```bash
# Export your OpenRouter API key
export OPENROUTER_API_KEY="your-key-here"

# Create PostgreSQL table first
psql -c "CREATE TABLE scraped_pages (id SERIAL PRIMARY KEY, url TEXT, summary TEXT, fetched_at TIMESTAMP);"

# Run the graph
ainl run multi_adapter.ainl --input '{"url": "https://news.ycombinator.com", "slack_webhook": "https://hooks.slack.com/..."}'
```

**Expected output**:
```json
{
  "url": "https://news.ycombinator.com",
  "summary": "Hacker News front page shows tech stories...",
  "stored_id": 42,
  "notified": true
}
```

---

## Step 4: Validate with Different Adapters

Try swapping the LLM adapter:

```bash
# Switch to Ollama (local)
export AINL_ADAPTER=ollama
export OLLAMA_MODEL=llama3.2

ainl run multi_adapter.ainl --input test.json
```

Notice: Only the `summarize` node uses the LLM adapter. The HTTP and SQL nodes use their configured adapters (`builtin.http`, `builtin.postgres`) independently.

---

## Step 5: Understanding Adapter Selection

From the graph, AINL determines adapters as:

| Node Type | Default Adapter | Override | How It's Chosen |
|-----------|-----------------|----------|-----------------|
| `LLM(...)` | `ainl.adapter` from config (`openrouter`) | `adapters.llm` | Global LLM adapter |
| `HTTP(...)` | `builtin.http` | `adapters.http` | Named adapter from config |
| `SQL(...)` | `builtin.postgres` | `adapters.sql` | Named adapter from config |
| `Cache(...)` | `builtin.cache.filesystem` | `adapters.cache` | Named adapter |

**Key insight**: You can mix and match. LLM uses OpenRouter, but HTTP and SQL use their own built-in adapters. No conflict.

---

## Step 6: Create a Custom Adapter (Optional)

Want to use a different database? Create custom PostgreSQL adapter:

```python
# adapters/my_postgres.py
import psycopg2
from ainl import Adapter

class MyPostgresAdapter(Adapter):
    def connect(self, config):
        self.conn = psycopg2.connect(config.connection_string)
    
    def execute(self, query, params):
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    
    def close(self):
        self.conn.close()
```

Configure it:

```yaml
adapters:
  postgres: my_postgres.MyPostgresAdapter
  postgres.connection_string: ${DATABASE_URL}
```

---

## Step 7: Production Considerations

### Error Handling

Add `try/catch`:

```ainl
node fetch: try(HTTP("fetch")) {
  on_error: log_error
  value: fetch_successful
}
```

### Adapter Pooling

For high-throughput, configure connection pooling:

```yaml
adapters:
  postgres:
    class: builtin.postgres
    pool_size: 10
    pool_recycle: 3600
```

### Cost Monitoring

Track LLM tokens:

```ainl
node summarize: LLM("summarize") {
  token_budget: 100  # Hard limit
  on_budget_exceeded: truncate_and_warn
}
```

---

## ✅ Checklist

You've completed the tutorial when:
- [x] Graph runs successfully with 3+ different adapter types
- [x] Configuration separates LLM, HTTP, and SQL adapters
- [x] PostgreSQL table created and data inserted
- [x] Tested with both OpenRouter and Ollama (at least one swap)
- [x] Error handling added to at least one node
- [x] Graph validates with `ainl validate multi_adapter.ainl`

---

## Next Steps

- Build your own multi-adapter graph (try Redis cache, file system, etc.)
- Read [adapters/README.md](../README.md) for deeper adapter creation
- Explore [patterns/email-alert-classifier.md](../patterns/email-alert-classifier.md) for real-world multi-adapter usage

---

**Questions?** Join #intermediate on Discord or start a GitHub Discussion.
