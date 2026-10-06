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
run run_case.py
run test_invariants.py
run run_goals.py --repeats "$REPEATS"
run independent_mapping.py
run figures/make_fig_sequence.py
