#!/usr/bin/env bash
# Check whether GitHub Discussions are enabled; post bodies live in docs/community/DISCUSSIONS_POST_EXACT.md
set -euo pipefail
gh api graphql -f query='query { repository(owner:"sbhooley", name:"ainativelang") { hasDiscussionsEnabled url } }' --jq '.data.repository'
echo "Paste title + body from docs/community/DISCUSSIONS_POST_EXACT.md into https://github.com/sbhooley/ainativelang/discussions/new"
echo "When hasDiscussionsEnabled is true, GraphQL createDiscussion can automate this — see GitHub docs for CreateDiscussionInput."
