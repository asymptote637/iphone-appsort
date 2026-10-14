#!/usr/bin/env bash
# Prefer a project-local Python; never install into the system runtime.
appsort_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
appsort_python=""
for appsort_candidate in "$appsort_root/.venv/bin/python" "${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3 || true)"; do
  if [ -x "$appsort_candidate" ] && "$appsort_candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
    appsort_python="$appsort_candidate"
    break
  fi
done
if [ -z "$appsort_python" ]; then
  printf '%s\n' '需要 Python 3.11 或更新版本。可从 python.org 安装，再启动本工具。' >&2
  return 1
fi
