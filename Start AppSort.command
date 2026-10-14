#!/usr/bin/env bash
set -euo pipefail
appsort_root="$(cd "$(dirname "$0")" && pwd)"
exec "$appsort_root/bin/appsort" serve
