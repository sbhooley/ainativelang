# Apollo Promoter AINL Module Contracts

This page documents the reusable AINL modules introduced while thinning `apollo-x-bot` Python prompt logic.

## `modules/common/promoter_persona_prompt.ainl`

- Frame in:
  - `ppp_mode` (`"post"` or `"reply"`, optional; defaults to `"post"`)
- Env:
  - `PROMOTER_PERSONA_PROFILE` (`default`, `fity`)
- Returns:
  - Persona instruction string (empty string for `default`)
- Notes:
  - `fity` is intentionally **AINL/graph-centric** (concrete wiring, adapters, deterministic workflows) rather than generic “agent” hype.

## `modules/llm/promoter_reply_prompt_bundle.ainl`

- Frame in:
  - `prb_mode` (`"tweet"` or `"thread"`, optional; defaults to `"tweet"`)
  - `prb_text` (source text for user prompt body)
- Returns object:
  - `reply_system_prompt`
  - `reply_user_prompt`
  - `reply_fallback_text`
- Notes:
  - Applies persona instructions from `promoter_persona_prompt.ainl`.
  - Uses `PROMOTER_CANONICAL_GITHUB_URL` when composing fallback/link text.
  - Reply prompts are tuned to be **concrete and opinionated** (mention AINL explicitly; reference node wiring/failure modes when useful).

## `modules/llm/promoter_process_tweet_payload.ainl`

- Frame in:
  - `ppt_tweet` (tweet object from poll pipeline)
- Returns object:
  - `payload` (tweet object)
  - `reply_system_prompt`
  - `reply_user_prompt`
  - `reply_fallback_text`
- Notes:
  - Delegates prompt composition to `promoter_reply_prompt_bundle.ainl` with `prb_mode="tweet"`.

## `modules/llm/promoter_thread_continue_payload.ainl`

- Frame in:
  - `ptc_tweets` (conversation tweet array)
  - `ptc_reply_to_tweet_id`
  - `ptc_conversation_id`
- Returns object:
  - `tweets`
  - `reply_to_tweet_id`
  - `conversation_id`
  - `reply_system_prompt`
  - `reply_user_prompt`
  - `reply_fallback_text`
- Notes:
  - Delegates prompt composition to `promoter_reply_prompt_bundle.ainl` with `prb_mode="thread"`.

## Gateway Expectations

Python handlers should treat these prompt fields as first-class payload inputs and only use internal prompt defaults as fallback safety for non-AINL callers.

## Policy Keys and Cost-Saving Behavior

- Policy KV keys:
  - `promoter_daily_block_flag`
  - `promoter_daily_fallback_model_flag`
  - `promoter_reply_fallback_model_flag`
  - `promoter_reply_skip_target_<user_id>`
- Value format:
  - JSON string object with `until_ts` and `action`
  - Legacy scalar values are treated as stale and cleared by guards/cleanup
- AINL short-circuit behavior:
  - `ainl-x-promoter` checks skip-target and fallback flags before `promoter.gate_eval` in the reply loop to avoid unnecessary calls.
  - Daily fallback flag causes static daily payload path and records `daily_post_fallback_model_active`.
  - Daily block guard treats `kv.get(...).body.value = null` as **not blocked**; only non-empty flag values activate the defer path.
- Dashboard/ops:
  - `GET /v1/promoter.stats` includes:
    - `policy_actions_normalized_last_24h`
    - `cost_avoidance_last_24h` (`llm_calls_avoided`, `x_calls_avoided_est`)
  - `POST /v1/promoter.policy_cleanup` clears stale policy flags and records `policy_flags_cleanup`.
