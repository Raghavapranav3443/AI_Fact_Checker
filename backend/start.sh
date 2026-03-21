#!/bin/bash
# Run from: veritas/backend/
set -e

echo "Starting Veritas backend..."
cd "$(dirname "$0")"

if [ ! -f venv/bin/activate ]; then
  echo "Creating virtualenv..."
  python3 -m venv venv
  venv/bin/pip install fastapi uvicorn "langgraph>=0.2" "langchain-core>=0.3" \
    tavily-python google-generativeai google-genai groq httpx \
    beautifulsoup4 lxml python-dotenv aiohttp
fi

if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example and fill in your API keys."
  exit 1
fi

echo "Backend running at http://localhost:8000"
echo "API docs at      http://localhost:8000/docs"
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
