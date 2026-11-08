# Decision graphs and the firm grant (1.8.2)

This is the current contract for strict decision graphs in this tree (`ainativelang` **1.8.2**, unreleased until a GitHub Release publishes it). `EQ`, `CONTAINS`, `TRIM`, `If`, and `Loop` are unchanged. New names and host grants carry the safer behavior.

Tests: `tests/test_firm_contract.py`, `tests/test_decision_ops_181.py`, `tests/test_regex_dialect.py`, `tests/test_http_adapter_contracts.py`.

## What stayed

| Surface | Behavior that still holds |
|---------|---------------------------|
| `R core.EQ` | Coerces through `float`. A quoted `"1"` equals `1`. |
| `R core.CONTAINS` | An empty needle is true. |
| `R core.TRIM` | Collapses internal whitespace. `X core.trim` only strips the edges. |
| `Loop` | A `J` inside the body stores `_loop_last` and continues. The `after` label's return wins. `J` does not stop the loop. |
| `If` | A `J` on the taken branch returns from the caller. |
| Truthiness | `None`, `False`, `0`, `""`, `[]`, and `{}` are false. `"0"` and `"false"` are true. |
| Token cap | Counts `usage` on the completion **return value** only. A missing `usage` adds 0. Counts stored on the adapter object are invisible. |
| HTTP allowlist | One exact host. `*` and `*.example.com` are not wildcards. |
| `db` | `db.Q` and `db.M` are the call shape. This tree does not speak Cosmos. |

## New core verbs

Safe replacements, all on `core`:

- `EQS` — no coercion after the argument is resolved. A quoted `"1"` is still coerced to a number before the op, so `R core.EQS "1" 1` stays true. A frame string `"1"` does not.
- `HAS` — an empty needle is false.
- `CONTAINS_WORD`, `REPLACE_CHARS`, `IN`.
- `Break` — stops the loop. `J` does not.
- `R core.IF` — value select. It does not jump.
- `REGEX_CONTAINS`, `REGEX_REPLACE`, `REGEX_FINDALL` — dialect `ainl.re.1` in `runtime/bounded_regex.py`. This is not Python `re`. Pattern cap 256, haystack cap 100000, step cap 100000. A size or step limit returns `{error:{code,message}}` and does not fail the document. Syntax errors still raise. Fixtures: `tests/fixtures/ainl_re_1.json`.
- `PARSE_TIME` — offsets, truncated fractional seconds, naive values as UTC, and `Nov 7, 2026`. The string `"now"` reads the injected clock.
- `ADD_DAYS` — `days * 86400` UTC. It is not a local civil calendar.
- `BEFORE`, `CASEFOLD`, `NORMALIZE`, `HTML_TEXT`, `IS_ERROR`.
- `HTML_TEXT` strips tags. It is not safe to render.
- `R`-path `PUT` and `PUSH`.

`MAP`, `FILTER`, and `REDUCE` run over a same-file label. That label stays pure (`core` only, and not `NOW`, `ISO`, `ISO_TS`, `ENV`, `SLEEP`, or `UUID`) unless `limits.allow_effectful_map` is set.

A quoted word does not read a frame key of the same name. `$name` and a bare word do.

## `Uses`

Opt-in. A file with no `Uses` line is unchanged, so the existing corpus still compiles.

```ainl
Uses core llm
```

Compact form, before the first label:

```ainl
uses: core, llm
```

When `Uses` is present, compile fails if an `R`, `X`, `QueuePut`, or cache step names an adapter the file did not declare. The host allowlist still applies. The intersection is what runs. A second `Uses` line is an error. The declaration belongs before the first label. Inside a label, strict mode auto-closes the label.

## `AINL_SECURITY_PROFILE=firm`

Named profile in `tooling/security_profiles.json`. It is not the default for `ainl run`. Set the env var. `ainl run` merges the profile with the CLI grant, and the CLI can only tighten it.

| | |
|--|--|
| Allow | `core`, `llm`, `db`, `queue` |
| Deny adapters | `http`, `web`, `fs`, `ext`, `extras`, `a2a`, `agent`, `svc`, `sqlite`, `postgres`, `mysql`, `redis`, `dynamodb`, `airtable`, `supabase`, `email`, `calendar`, `social`, `tiktok`, `tools`, `llm_query`, `embedding_memory`, `ptc_runner`, `browser` |
| Deny verbs | `db.D`, `core.ENV` (`denied_verbs` is a grant field; merge unions it, so a caller cannot remove an entry) |
| Privilege | `operator_sensitive` forbidden |
| Limits | `max_steps` 50000, `max_depth` 50, `max_adapter_calls` 500, `max_time_ms` 120000, `max_frame_bytes` 1048576, `max_completion_calls` 8, `max_completion_tokens` 32000, `max_query_rows` 25, `max_query_bytes` 262144 |

`db.D` stays in the catalog for other consumers. The firm profile denies it at runtime (`FIRM_VERB`). The engine does not auto-load this profile from the environment on every `RuntimeEngine`; the CLI, runner, and MCP pass `denied_verbs` when a profile is loaded.

Runner and MCP default grants include the four completion and query caps even when no profile is set. `merge_grants` takes the minimum, so a POST body cannot raise them. An in-process `RuntimeEngine.from_code(limits=...)` can still raise the cap. That is how tests do it. The graph cannot.

## Prompt, shape, queue, clock

```ainl
R core.UNTRUSTED_PROMPT instructions document ->prompt
R core.SHAPE obj "answer:string" "score:number" ->out
R queue.PUT name message key ->_
```

- `UNTRUSTED_PROMPT` keeps the document in its own block. A copy of the end marker inside the document is broken so it cannot close the block. Over 100000 characters returns `{error:{code:UNTRUSTED_LIMIT}}` and does not include the document. This is `core`. It is not a completion.
- `SHAPE` types: `string`, `number` (int or float, not bool), `bool`, `object`, `array`, `any`. A missing field is `{error:{code:SHAPE_MISSING}}`. The message names the field, not the model object. Success returns a new dict of only the declared fields.
- `queue.PUT` keeps the two-argument form. A third argument is the idempotency key: a non-empty string, or `QUEUE_IDEMPOTENCY`. On a dict message the runtime stamps `idempotency_key` (setdefault on a copy) and passes `[queue, message, key]` to the adapter. A non-dict message is unchanged. The opcode `QueuePut` form is unchanged and does not take the key.
- `limits["now"]` is the unix second for `NOW`, `ISO`, `ISO_TS` with no argument, and `PARSE_TIME "now"`. The runtime stamps it on the adapter context after copying the frame, so `Set _now` cannot widen it. `ADD_DAYS` stays `days * 86400` UTC.

## Secrets and cloud-key literals

`core.ENV` is default deny (`limits.env_allowlist`). `X core.ENV` uses that same host list in any letter case. A graph cannot install its own allowlist with `Set _env_allowlist`.

Secret-shaped names are refused even when allowlisted. The message is `core.ENV cannot read a secret` and does not include the value. That includes `AWS_SECRET_ACCESS_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SESSION_TOKEN`, `AZURE_CLIENT_SECRET`, and platform names that do not look like a generic secret: `AzureWebJobsStorage`, `SQLAZURECONNSTR_*`, `SQLCONNSTR_*`, `MYSQLCONNSTR_*`, `CUSTOMCONNSTR_*`, `POSTGRESQLCONNSTR_*`, `APPINSIGHTS_INSTRUMENTATIONKEY`, `DATABASE_URL`, `REDIS_URL`, `MONGO_URI`, and `AINL_POSTGRES_URL` / `AINL_MYSQL_URL` / `AINL_REDIS_URL`.

A string literal that looks like a cloud key fails the compile. The diagnostic is `string literal looks like a cloud key` and does not contain the key. The scan covers the preprocessed source, including comments. Patterns include `AKIA`/`ASIA` plus 16 characters, `AccountKey=`, `DefaultEndpointsProtocol=`, `SharedAccessSignature`, `BEGIN PRIVATE KEY`, `sk-ant-` and long `sk-` tokens, `ghp_` / `github_pat_`, `xoxb-`/`xoxa-`/`xoxp-`/`xoxr-`/`xoxs-`, `AIza` plus 30 characters, and `ya29.`.

## HTTP

`SimpleHttpAdapter()` with no arguments is deny-by-default:

- HTTPS only, private-address blocking, redirect re-check, status returned as a value.
- Empty `allow_hosts` denies every host. `*` is not an entry.
- At most 3 redirects. Timeout 5 seconds. Response cap 1000000 bytes. Both must be positive and finite (`nan` and `inf` are rejected).
- The connect is pinned to an address the adapter already checked. A `Host` header from the graph is dropped.
- A cross-host redirect drops `Authorization`, `Cookie`, `Proxy-Authorization`, `X-Api-Key`, `Api-Key`, and `X-Amz-Security-Token`.

Metadata stays closed even when private addresses are allowed: `169.254.169.254`, `169.254.170.23`, `168.63.129.16` (Azure Wire Server), `192.0.0.192` (Oracle), link-local, IPv4-mapped forms, 6to4, and NAT64 `64:ff9b::/96` of a metadata address. Loopback and RFC1918 can still open under `allow_insecure_local`. `100.64.0.0/10` is not blocked as a whole. Alibaba `100.100.100.200` is.

CLI, MCP, and the runner force private-address blocking. A test helper may opt out. That opt-out is not the production factory. Collectors that need an open host list stay in Python. Do not add a wildcard allowlist.

These other fetchers use the same public-host check. An empty allowlist denies. A listed loopback or private host may be fetched. Metadata never is, even if listed.

| Caller | Allowlist |
|--------|-----------|
| `llm_query`, `ptc_runner` | `allow_hosts` on the adapter. `ainl run` passes `--http-allow-host`. |
| Airtable attachment URLs | `allow_attachment_hosts`. An empty list denies. HTTPS only. |
| `extras.http_status` | `AINL_EXTRAS_HTTP_ALLOW_HOSTS`. No shell `curl` and no raw `urlopen`. |
| Pyth Hermes price URL | The Hermes base hostname. HTTPS only. |

## A2A

An empty `allow_hosts` denies every host (`a2a: empty allowlist denies every host`). `follow_redirects=False` does not follow a redirect.

Hermes `discover_hermes` / `send_hermes` use a separate check: a **public** host, DNS checked, or a **loopback literal** (`127.0.0.1`, `::1`) from the operator's `a2a.json`. Private, link-local, and metadata addresses stay closed. The hostname `localhost` is still resolved and refused when it is not a literal loopback address the guard already accepted. A non-loopback lab peer needs the normal allowlist plus `allow_insecure_local`.

## Completion budget

Any adapter whose verb is `completion` or `embed` counts, including a provider registered under its own name (`openrouter.completion`). So do `llm_query` verbs `query` and `run`, and `embedding_memory` verbs `upsert_ref`, `index`, `search`, and `query`.

The default is 8 calls and 32000 tokens. `0` calls means no calls. Crossing the call cap raises `LLM_BUDGET` before the request. Crossing the token cap raises after the call that crossed. Cross-file calls share the budget. The host raises the cap through `limits` on `from_code`. The graph cannot.

## Traces and the runner log

`safe_trace` defaults on. The trace omits `out` and `frame_keys`. The conformance runner passes `safe_trace=False`.

The runner JSON log for `adapter_call` records `arg_count` and `arg_types`. It does not record argument values. The HTTP response field `adapter_calls`, when the caller asked to record calls, still comes from the redacted call log. Replay uses that log, not the JSON line.

## What stays on the host

Short-lived identity, no prompt or response logging, a token alarm, least privilege, and no long-lived client secret. IMDSv2 hop limits, IAM, SCPs, VPC endpoints, Azure managed identity, `disableLocalAuth`, Conditional Access, Azure Policy, Wire Server NSGs, GCP metadata concealment, and workload identity are account controls. This compiler does not patch them.
