#!/bin/bash
# Run from: veritas/frontend/
set -e

echo "Starting Veritas frontend..."
cd "$(dirname "$0")"

if [ ! -d node_modules ]; then
  echo "Installing dependencies..."
  npm install --legacy-peer-deps
fi

echo "Frontend running at http://localhost:5173"
npm run dev
