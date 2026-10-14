#!/usr/bin/env bash
set -euo pipefail
appsort_root="$(cd "$(dirname "$0")" && pwd)"
"$appsort_root/bin/setup"
if [ -t 0 ]; then read -r -p 'Press Return to close…' appsort_reply; fi
