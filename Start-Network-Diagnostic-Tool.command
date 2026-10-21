#!/bin/bash
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python 3.10+ and try again."
  exit 1
fi
exec python3 -m netdiag.dashboard "$@"
