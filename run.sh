#!/usr/bin/env bash
set -eu
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
export PYTHONPATH="$project_dir/src${PYTHONPATH:+:$PYTHONPATH}"
exec .venv/bin/python -m alma_libcal "$@"
