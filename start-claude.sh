#!/bin/zsh

if echo "$PWD" | grep -q '/Desktop/repos/clients/'; then
  echo "Syncing library versions..."
  find /Users/yagiz.yaman/Desktop/repos/products -maxdepth 1 -mindepth 1 -type d | while read repo; do
    git -C "$repo" checkout . 2>/dev/null
    git -C "$repo" reset --hard 2>/dev/null
    git -C "$repo" clean -fd 2>/dev/null
  done
  python3 /Users/yagiz.yaman/Desktop/repos/utilities/sync-libs.py
  echo "Sync complete. Starting Claude..."
fi

claude "$@"
