#!/bin/zsh

CLAUDE_BIN="/Users/yagiz.yaman/.local/bin/claude"

[[ -t 0 ]] || exec "$CLAUDE_BIN" "$@"

MCP_PROFILES_DIR="/Users/yagiz.yaman/Desktop/repos/utilities/mcp-profiles"

# Parse --profile / -P and --no-prompt before passing remaining args to claude
PROFILE=""
NO_PROMPT=0
CLAUDE_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile|-P)
      PROFILE="$2"
      shift 2
      ;;
    --no-prompt)
      NO_PROMPT=1
      shift
      ;;
    *)
      CLAUDE_ARGS+=("$1")
      shift
      ;;
  esac
done

# If no explicit profile and prompt not suppressed, ask interactively
if [[ -z "$PROFILE" && $NO_PROMPT -eq 0 ]]; then
  PROFILES=()
  for f in "$MCP_PROFILES_DIR"/*.json; do
    [[ -f "$f" ]] && PROFILES+=("$(basename "$f" .json)")
  done

  if [[ ${#PROFILES[@]} -gt 0 ]]; then
    # Build display labels from _label field in JSON, fallback to filename
    LABELS=()
    for p in "${PROFILES[@]}"; do
      f="$MCP_PROFILES_DIR/$p.json"
      label="$(python3 -c "import json; d=json.load(open('$f')); print(d.get('_label', '$p'))" 2>/dev/null || echo "$p")"
      LABELS+=("$label")
    done
    LABELS+=("use all mcp servers")

    echo ""
    echo "Which MCP servers do you need?"
    select choice in "${LABELS[@]}"; do
      if [[ "$choice" == "use all mcp servers" || -z "$choice" ]]; then
        break
      elif [[ -n "$choice" ]]; then
        # $REPLY is the 1-based index; PROFILES is also 1-based in zsh
        PROFILE="${PROFILES[$REPLY]}"
        break
      fi
    done
  fi
fi

if echo "$PWD" | grep -qi '/Desktop/repos/clients/'; then
  echo "Syncing library versions..."
  python3 /Users/yagiz.yaman/Desktop/repos/utilities/sync-libs.py
  echo "Sync complete."
fi

# Launch claude
if [[ -n "$PROFILE" ]]; then
  PROFILE_FILE="$MCP_PROFILES_DIR/$PROFILE.json"
  if [[ ! -f "$PROFILE_FILE" ]]; then
    echo "Unknown profile: $PROFILE"
    echo "Available: $(ls "$MCP_PROFILES_DIR"/*.json 2>/dev/null | xargs -I{} basename {} .json | tr '\n' ' ')"
    exit 1
  fi
  PROFILE_LABEL="$(python3 -c "import json; d=json.load(open('$PROFILE_FILE')); print(d.get('_label', '$PROFILE'))" 2>/dev/null || echo "$PROFILE")"
  echo "Starting Claude — MCP: ${PROFILE_LABEL}."
  "$CLAUDE_BIN" --mcp-config "$PROFILE_FILE" --strict-mcp-config "${CLAUDE_ARGS[@]}"
else
  echo "Starting Claude — MCP: all servers."
  "$CLAUDE_BIN" "${CLAUDE_ARGS[@]}"
fi
