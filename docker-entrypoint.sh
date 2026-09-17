#!/usr/bin/env bash
# Wait for the database (when one is configured), seed it, then serve the app.
set -euo pipefail

if [[ "${DATABASE_URL:-}" == postgres* ]]; then
  echo "Waiting for PostgreSQL…"
  for _ in $(seq 1 40); do
    if python -c "
import sys
from sqlalchemy import create_engine, text
try:
    create_engine('${DATABASE_URL}').connect().execute(text('SELECT 1'))
except Exception:
    sys.exit(1)
" 2>/dev/null; then
      echo "PostgreSQL is ready."
      break
    fi
    sleep 2
  done
fi

echo "Seeding CaseBrief…"
python scripts/seed_database.py ${SEED_ARGS:---analyse}

echo "Starting Streamlit on :8501"
exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
