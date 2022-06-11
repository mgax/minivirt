#!/bin/bash

set -euo pipefail

cd "$( dirname "${BASH_SOURCE[0]}" )"
source .venv/bin/activate

export MINIVIRT_DB=$(pwd)/.minivirt
export PYTHONUNBUFFERED=yesplease

exec python3 -m minivirt "$@"
