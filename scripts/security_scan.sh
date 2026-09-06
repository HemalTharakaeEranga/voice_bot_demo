#!/usr/bin/env bash
set -euo pipefail

python -m ruff check app tests
python -m bandit -r app -lll
python -m pip_audit -r requirements.txt
python -m pytest

echo "Security and quality checks completed. Review all findings before release."
