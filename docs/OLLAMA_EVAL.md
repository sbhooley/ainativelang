# Local Ollama Evaluation

Use this harness to measure whether a local model can generate valid AINL quickly and reliably.

## Prerequisites

- Ollama running locally (`http://127.0.0.1:11434`)
- A pulled model (example: `qwen2.5:7b`)
- Project installed (`pip install -e ".[dev]"`)

## Run evaluation

```bash
ainl-ollama-eval --model qwen2.5:7b --prompts data/evals/ollama_prompts.jsonl
```

Output:

- Console JSON summary
- Report file: `data/evals/ollama_eval_report.json`

## Metrics included

- `pass_rate`: strict compile success rate
- per-case `error_count` and sample `errors`
- generated character count and IR stats

## Extend prompts

Add JSONL lines to `data/evals/ollama_prompts.jsonl`:

```json
{"id":"my_case","prompt":"Create AINL for ..."}
```

## Agent loop integration

Pair this with `ainl-tool-api` and the tool API schema at:

- `tooling/ainl_tool_api.schema.json`
