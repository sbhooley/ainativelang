#!/usr/bin/env python3
"""Test promoter daily post content generation without posting."""
import os, json, requests

# Load env from apollo-x-promoter.env
env_file = '/Users/clawdbot/.openclaw/apollo-x-promoter.env'
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ[k] = v

GATEWAY = os.getenv('PROMOTER_GATEWAY_URL', 'http://127.0.0.1:17307')

def post(endpoint, body=None):
    url = f"{GATEWAY}/v1/{endpoint}"
    resp = requests.post(url, json=body or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()

try:
    # 1. Get snippets
    snippets_resp = post('promoter.daily_snippets')
    snippets = snippets_resp.get('snippets', '')
    print("SNIPPETS (truncated):", snippets[:500])

    # 2. Get commits
    commits_resp = post('promoter.daily_github_commits')
    commits = commits_resp.get('commits', [])
    print("COMMITS:", commits)

    # 3. Get persona prompts (system and user suffix)
    prompts = post('promoter.daily_post_prompts')
    system = prompts.get('system', '')
    user_suffix = prompts.get('user_suffix', '')
    print("SYSTEM PROMPT (truncated):", system[:300])
    print("USER SUFFIX:", user_suffix)

    # Build user message as the actual chain does
    user_message = ""
    if snippets:
        user_message += "Repository excerpts:\n" + snippets + "\n\n"
    if commits:
        user_message += "Recent commits:\n" + "\n".join(commits) + "\n\n"
    user_message += user_suffix

    # 4. Call LLM chat directly (match promoter config)
    llm_payload = {
        "model": os.getenv('LLM_MODEL', 'gpt-4o-mini'),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.72,  # matches PROMOTER_DAILY_POST_TEMPERATURE default
        "max_tokens": int(os.getenv('PROMOTER_LLM_MAX_COMPLETION_TOKENS', 512))
    }
    llm_resp = requests.post(f"{GATEWAY}/v1/llm.chat", json=llm_payload, timeout=60)
    llm_resp.raise_for_status()
    result = llm_resp.json()
    print("\n=== LLM RAW RESPONSE ===")
    print(json.dumps(result, indent=2))
    if result.get('ok'):
        text = result.get('text', '').strip()
        print("\n=== GENERATED TEXT ===")
        print(text)
        print(f"\nCharacter count: {len(text)}")
    else:
        print("LLM call failed:", result.get('error'))
except Exception as e:
    print("Error:", e)
    import traceback; traceback.print_exc()
