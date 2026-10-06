#!/usr/bin/env bash
# Reproduce the evaluation inside the Compose stack (docker compose up -d first).
#   ./evaluate.sh              3 executions per goal
#   REPEATS=5 ./evaluate.sh    more executions per goal
set -euo pipefail
cd "$(dirname "$0")"
REPEATS="${REPEATS:-3}"
run() {
  docker compose run --rm -T \
    -v "$PWD/output:/app/output" -v "$PWD/figures:/app/figures" \
    agent python "$@"
}
run experiments/run_case.py
run experiments/test_invariants.py
run experiments/run_goals.py --repeats "$REPEATS"
run experiments/independent_mapping.py
run figures/make_fig_sequence.py
