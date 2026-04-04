#!/usr/bin/env bash
# Study Companion AI — End-to-End Demo
# Usage: bash scripts/demo.sh

set -e

echo "=== Study Companion AI — Demo ==="

# Run pipeline on sample
echo "[1] Running pipeline on sample PDF..."
bash scripts/run_pipeline.sh examples/sample_input.pdf

# Start API
echo ""
echo "[2] Starting API server..."
uvicorn api.main:app --port 8000 &
API_PID=$!
sleep 3

# Health check
echo "[3] Health check..."
curl -s http://localhost:8000/health | python -m json.tool

# Generate study material
echo ""
echo "[4] Generating study material..."
curl -s -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "photosynthesis", "mode": "simple_explanation"}' | python -m json.tool

echo ""
echo "[5] Generating key concepts..."
curl -s -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Calvin Cycle", "mode": "key_concepts"}' | python -m json.tool

# Cleanup
echo ""
echo "[6] Stopping API server..."
kill $API_PID 2>/dev/null || true

echo ""
echo "=== Demo Complete ==="
echo "To run the full app:"
echo "  uvicorn api.main:app --port 8000 &"
echo "  streamlit run ui/app.py"
