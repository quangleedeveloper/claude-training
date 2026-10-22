#!/bin/bash
# Shared production-deploy gate, sourced by validate-bash.sh and validate-prompt.sh
# so the approval rule lives in one place.

DEPLOY_APPROVAL_MESSAGE="Production deployment requires approval. Create .deployment-approved file to proceed."

# The approval file lives at the repo root, whatever directory the command runs from.
deployment_approved() {
  local root
  root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
  [ -f "${root:-.}/.deployment-approved" ]
}
