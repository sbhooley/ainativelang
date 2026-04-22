# AINL Adapter Catalog

Complete reference for all 43 adapters available in AI_Native_Lang.

## Core Adapters (4)

### core
**Foundation operations** - Variables, control flow, data structures
- **Targets:** SET, GET, LEN, APPEND, LIST, DICT, KEYS, VALUES, MERGE, FILTER, MAP, REDUCE, RANGE, CONTAINS, TYPE_OF, TO_STRING, TO_INT, TO_FLOAT, PARSE_JSON, TO_JSON, SPLIT, JOIN, SLICE, CONCAT, FLATTEN, UNIQUE, SORT, REVERSE, ZIP, ENUMERATE, GROUP_BY, SET_MULTI
- **Example:** Used in every AINL program for basic operations
- **Network:** No | **Side Effects:** None

### noop
**No operation** - Returns empty dict, used for placeholder/testing
- **Targets:** noop
- **Network:** No | **Side Effects:** None

### debug
**Debugging utilities** - Print, inspect, assert, breakpoint
- **Targets:** print, inspect, assert, breakpoint, log
- **Example:** `R debug.print "Debug output" ->result`
- **Network:** No | **Side Effects:** Logs/prints to stderr

### error
**Error handling** - Raise, catch, retry mechanisms
- **Targets:** raise, catch, retry, is_error
- **Network:** No | **Side Effects:** May terminate execution

## File System (3)

### fs
**File system operations** - Read, write, list, delete files
- **Targets:** READ, WRITE, DELETE, LIST, EXISTS, MKDIR, RMDIR, COPY, MOVE, STAT, CHMOD
- **Example:** `R fs.READ "/path/file.txt" ->content`
- **Network:** No | **Side Effects:** Modifies file system

### path
**Path manipulation** - Join, dirname, basename, resolve
- **Targets:** join, dirname, basename, exists, resolve, ext
- **Network:** No | **Side Effects:** None

### iofs
**I/O operations** - stdin, stdout, file descriptors
- **Targets:** read_stdin, write_stdout, read_file, write_file
- **Network:** No | **Side Effects:** I/O operations

## Network & APIs (8)

### http
**HTTP client** - GET, POST, PUT, DELETE requests
- **Targets:** get, post, put, delete, request
- **Example:** `examples/http_example.ainl`
- **Network:** Yes | **Side Effects:** External HTTP calls

### a2a
**A2A (Agent-to-Agent) client** - Agent Card discovery, JSON-RPC `tasks/send` and `tasks/get` (ArmaraOS wire)
- **Targets:** discover, send, get_task
- **Example:** `examples/compact/a2a_delegate.ainl`
- **Config:** `ainl run` uses `--a2a-allow-host`, `--a2a-allow-insecure-local`, `--a2a-strict-ssrf`, `--a2a-follow-redirects`; or env `AINL_A2A_*` (see [docs/integrations/A2A_ADAPTER.md](docs/integrations/A2A_ADAPTER.md))
- **Network:** Yes | **Side Effects:** Outbound HTTP only

### api
**Generic REST API wrapper** - Configurable HTTP with auth
- **Targets:** call, get, post, put, delete
- **Example:** `examples/api_example.ainl`
- **Config:** `AINL_API_BASE_URL`, `AINL_API_TOKEN`
- **Network:** Yes | **Side Effects:** External API calls

### email
**Email integration** - IMAP/SMTP with threading, attachments, HTML
- **Targets:** send, read, search, reply, draft, G (OpenClaw legacy)
- **Examples:** `examples/email_send_example.ainl`, `examples/email_reply_example.ainl`, `examples/email_html_example.ainl`, `examples/email_attachment_example.ainl`
- **Config:** `EMAIL_SMTP_HOST`, `EMAIL_IMAP_HOST`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`
- **Features:** ✅ HTML email, ✅ Attachments, ✅ Threading (In-Reply-To), ✅ Drafts
- **Network:** Yes | **Side Effects:** Sends/reads emails

### web
**Web scraping** - Fetch and parse web pages
- **Targets:** G (get page content)
- **Example:** `R web.G "https://example.com" ->html`
- **Network:** Yes | **Side Effects:** HTTP requests

### github
**GitHub API** - Repos, issues, pull requests
- **Targets:** get_repo, list_issues, create_issue, get_pr
- **Example:** `examples/github_example.ainl`
- **Config:** `GITHUB_TOKEN`
- **Network:** Yes | **Side Effects:** May create/modify GitHub resources

### webhook
**Webhook receiver** - Listen for HTTP callbacks
- **Targets:** listen, respond
- **Network:** Yes | **Side Effects:** Opens HTTP server

### graphql
**GraphQL client** - Query and mutation execution
- **Targets:** query, mutate
- **Network:** Yes | **Side Effects:** External GraphQL calls

## Data & Storage (6)

### db
**Database operations** - Query, insert, update, delete
- **Targets:** query, insert, update, delete, transaction
- **Config:** `AINL_DB_URL`, `AINL_DB_TYPE` (postgres, mysql, sqlite)
- **Network:** Depends on DB | **Side Effects:** Modifies database

### kv
**Key-value store** - Get, set, delete key-value pairs
- **Targets:** get, set, delete, exists, keys, incr, decr
- **Config:** `AINL_KV_BACKEND` (redis, memcached, file)
- **Network:** Depends on backend | **Side Effects:** Modifies KV store

### cache
**Caching layer** - TTL-based caching
- **Targets:** get, set, delete, clear, ttl
- **Network:** No (in-memory) | **Side Effects:** Memory usage

### txn
**Transaction management** - Begin, commit, rollback
- **Targets:** begin, commit, rollback
- **Example:** Database transaction workflows
- **Network:** No | **Side Effects:** Transaction state

### queue
**Message queue** - Enqueue, dequeue, pub/sub
- **Targets:** enqueue, dequeue, peek, size, clear
- **Config:** `AINL_QUEUE_BACKEND` (rabbitmq, sqs, redis)
- **Network:** Depends on backend | **Side Effects:** Queue operations

### crm
**CRM integration** - Contacts, leads, opportunities
- **Targets:** create_contact, get_contact, update_contact, list_contacts
- **Config:** `AINL_CRM_PROVIDER` (salesforce, hubspot)
- **Network:** Yes | **Side Effects:** Modifies CRM data

## AI & Semantic (4)

### embedding_memory
**Semantic search** - Vector embeddings for RAG
- **Targets:** UPSERT_REF, SEARCH, REMOVE_REF
- **Example:** `examples/embedding_memory_example.ainl`
- **Config:** `AINL_EMBEDDING_MODE` (stub, local, openai), `OPENAI_API_KEY`
- **Network:** Depends on mode | **Side Effects:** Stores embeddings

### code_context
**Code analysis** - Tiered chunking (Tier 0/1/2)
- **Targets:** INDEX, QUERY_CONTEXT, GET_FULL_SOURCE, GET_CHUNK, COMPRESS_CONTEXT, CLEAR
- **Example:** `examples/code_context_example.ainl`
- **Config:** `AINL_CODE_CONTEXT_MAX_TIER` (default: 2)
- **Network:** No | **Side Effects:** Creates index files

### llm
**LLM provider** - OpenAI, Anthropic, etc.
- **Targets:** GENERATE, CHAT
- **Example:** `examples/llm_example.ainl`
- **Config:** `AINL_LLM_PROVIDER` (openai, anthropic), `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AINL_LLM_MODEL`
- **Network:** Yes | **Side Effects:** API calls, costs money

### langchain_tool
**LangChain integration** - Call @tool decorated functions
- **Targets:** CALL
- **Example:** `examples/langchain_tool_example.ainl`
- **Config:** `LANGCHAIN_TOOL_PATH` (Python module path)
- **Network:** Depends on tool | **Side Effects:** Depends on tool

## Execution & Process (4)

### ext
**Extensions/subprocess** - Execute shell commands
- **Targets:** echo, EXEC, RUN
- **Example:** `R ext.EXEC "ls -la" ->output`
- **Network:** No | **Side Effects:** Subprocess execution

### tools
**Tool invocation bridge** - Dynamic tool calling
- **Targets:** call, list, describe
- **Network:** Depends on tool | **Side Effects:** Depends on tool

### bridge
**Executor bridge** - Cross-runtime communication
- **Targets:** send, receive, status
- **Network:** Depends on transport | **Side Effects:** IPC/RPC calls

### worker
**Background workers** - Async task execution
- **Targets:** spawn, wait, status, cancel, result
- **Network:** No | **Side Effects:** Background processes

## Time & Scheduling (3)

### time
**Time operations** - Current time, formatting, parsing
- **Targets:** now, format, parse, sleep, timezone
- **Example:** `R time.now ->timestamp`
- **Network:** No | **Side Effects:** None (sleep blocks)

### timer
**Timers** - Scheduled execution, intervals
- **Targets:** set, clear, interval, timeout
- **Network:** No | **Side Effects:** Scheduled callbacks

### cron
**Cron scheduling** - Periodic task execution
- **Targets:** add, remove, list, run_now
- **Config:** `AINL_CRON_BACKEND` (system, internal)
- **Network:** No | **Side Effects:** Scheduled execution

## Security & Auth (3)

### auth
**Authentication** - Login, logout, token management
- **Targets:** login, logout, verify
- **Config:** `AINL_AUTH_PROVIDER`, `AINL_AUTH_SECRET`
- **Network:** Depends on provider | **Side Effects:** Auth state changes

### secrets
**Secret management** - Encrypted storage
- **Targets:** get, set, delete, list
- **Config:** `AINL_SECRETS_BACKEND` (vault, env, file)
- **Network:** Depends on backend | **Side Effects:** Secret storage

### crypto
**Cryptography** - Hash, encrypt, decrypt, sign
- **Targets:** hash, encrypt, decrypt, sign, verify
- **Example:** `R crypto.hash "sha256" "data" ->digest`
- **Network:** No | **Side Effects:** None

## Math & Computation (2)

### math
**Mathematical operations** - Trig, log, random
- **Targets:** add, sub, mul, div, mod, pow, sqrt, sin, cos, tan, log, exp, random, round, floor, ceil, abs, min, max
- **Example:** `R math.sqrt 144 ->result` (returns 12)
- **Network:** No | **Side Effects:** None

### stats
**Statistics** - Mean, median, std dev
- **Targets:** mean, median, mode, stddev, variance, percentile
- **Network:** No | **Side Effects:** None

## Blockchain (2)

### solana
**Solana blockchain** - Wallet, transactions, programs
- **Targets:** get_balance, send_transaction, get_account, deploy_program
- **Config:** `SOLANA_RPC_URL`, `SOLANA_KEYPAIR_PATH`
- **Network:** Yes | **Side Effects:** Blockchain transactions

### web3
**Ethereum/Web3** - Smart contracts, transactions
- **Targets:** call, send, deploy, estimate_gas
- **Config:** `WEB3_PROVIDER_URL`, `WEB3_PRIVATE_KEY`
- **Network:** Yes | **Side Effects:** Blockchain transactions

## Messaging (1)

### slack
**Slack integration** - Send messages, read channels
- **Targets:** send_message, read_channel, create_channel
- **Config:** `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`
- **Network:** Yes | **Side Effects:** Sends Slack messages

## Summary Statistics

- **Total Adapters:** 42
- **Network-enabled:** 15 (http, api, email, web, github, webhook, graphql, llm, db, kv, queue, crm, solana, web3, slack)
- **Side Effects:** 25 (modify external state)
- **Examples Created:** 12 (email x5, embedding_memory, code_context, langchain_tool, llm, github, api)

## Configuration Quick Reference

Key environment variables for commonly used adapters:

```bash
# Email
export EMAIL_USERNAME=your.email@gmail.com
export EMAIL_PASSWORD=app_specific_password

# LLM
export AINL_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# GitHub
export GITHUB_TOKEN=ghp_...

# Database
export AINL_DB_URL=postgresql://user:pass@host/db

# API
export AINL_API_TOKEN=your_token

# Embedding
export AINL_EMBEDDING_MODE=openai
export OPENAI_API_KEY=sk-...

# Adapter Security
export AINL_ALLOW_IR_DECLARED_ADAPTERS=1
# OR
export AINL_HOST_ADAPTER_ALLOWLIST=core,http,email,llm
```

## Example Programs

All examples located in `examples/`:

| Adapter | Example File | Description |
|---------|-------------|-------------|
| **email** | `email_send_example.ainl` | Basic email sending |
| **email** | `email_read_example.ainl` | Read inbox with filters |
| **email** | `email_autoresponder.ainl` | Auto-reply pattern |
| **email** | `email_reply_example.ainl` | Reply with threading |
| **email** | `email_draft_example.ainl` | Draft management |
| **email** | `email_html_example.ainl` | HTML email with fallback |
| **email** | `email_attachment_example.ainl` | Send attachments |
| **email** | `email_search_example.ainl` | IMAP search queries |
| **embedding_memory** | `embedding_memory_example.ainl` | Semantic RAG pattern |
| **code_context** | `code_context_example.ainl` | Code analysis |
| **langchain_tool** | `langchain_tool_example.ainl` | LangChain integration |
| **llm** | `llm_example.ainl` | LLM generation/chat |
| **github** | `github_example.ainl` | GitHub API usage |
| **api** | `api_example.ainl` | REST API calls |

## Usage Patterns

### Simple Automation (Core + FS + HTTP)
```ainl
R fs.READ "config.json" ->config
R core.PARSE_JSON config ->data
R http.post "https://api.example.com/webhook" data ->response
```

### AI-Powered Processing (LLM + Embedding)
```ainl
R embedding_memory.SEARCH "Python best practices" 5 ->docs
R llm.GENERATE "Summarize these docs: {docs}" 500 0.7 ->summary
```

### Email Workflow (Email + FS)
```ainl
R email.read "INBOX" 10 true "urgent@company.com" ->emails
R fs.WRITE "/tmp/urgent_emails.json" emails ->result
R email.send "team@company.com" "Urgent Emails Report" emails ->sent
```

### Data Pipeline (DB + Queue + Cache)
```ainl
R db.query "SELECT * FROM users WHERE active=true" ->users
R queue.enqueue "process_users" users ->queued
R cache.set "active_users_count" users.length 3600 ->cached
```

## Integration with ArmaraOS

AINL adapters integrate with ArmaraOS in two ways:

1. **Scheduled AINL Programs** - ArmaraOS daemon runs .ainl files with all adapters available
2. **Agent Tool Bridge** - ArmaraOS agents can invoke AINL programs as tools

See `docs/armaraos-integration.md` for details.

## Security Considerations

**Capability Gating:**
- All adapters respect `AINL_HOST_ADAPTER_ALLOWLIST` / `AINL_HOST_ADAPTER_DENYLIST`
- Set `AINL_ALLOW_IR_DECLARED_ADAPTERS=1` to auto-allow registry adapters
- Network-enabled adapters flagged with `"network": true` in registry

**Credential Management:**
- Use environment variables (not hardcoded)
- ArmaraOS encrypts secrets in config
- Use app-specific passwords for email (not main password)
- Rotate API tokens regularly

**Audit Trail:**
- Side-effect adapters log operations
- Database/blockchain transactions are immutable
- Email sends create Message-ID for tracking

## Next Steps

1. **Test Examples** - Validate and run example programs
2. **Custom Adapters** - Add project-specific adapters to registry
3. **ArmaraOS Integration** - Sync AINL library to `~/.armaraos/ainl-library/`
4. **Production Deployment** - Set up proper secret management

## Contributing

To add a new adapter:

1. Add definition to `ADAPTER_REGISTRY.json`
2. Implement in `adapters/your_adapter.py`
3. Create example in `examples/your_adapter_example.ainl`
4. Update this catalog with entry
5. Test with `ainl validate` and `ainl run`

See `docs/ADAPTERS.md` for implementation guide.
