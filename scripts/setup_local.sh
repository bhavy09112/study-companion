#!/usr/bin/env bash
# Study Companion AI — Local Setup Script
# Usage: bash scripts/setup_local.sh

set -e

echo "=== Study Companion AI — Local Setup ==="

# Check Python version
python --version 2>/dev/null || python3 --version || { echo "Python not found"; exit 1; }

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Verify critical imports
echo "Verifying imports..."
python -c "
import torch, transformers, peft, faiss, sentence_transformers
import fastapi, streamlit, genanki
print('All critical imports OK')
print('CUDA:', torch.cuda.is_available())
"

# Initialize database
echo "Initializing SRS database..."
python -c "from srs.db import init_db; init_db(); print('Database initialized')"

# Check Ollama
echo "Checking Ollama..."
if command -v ollama &>/dev/null; then
    echo "Ollama found:"
    ollama list 2>/dev/null || echo "  (no models pulled yet)"
else
    echo "Ollama not installed. Install from: https://ollama.ai"
    echo "Then run: ollama pull mistral"
fi

echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "  1. bash scripts/run_pipeline.sh examples/sample_input.pdf"
echo "  2. uvicorn api.main:app --port 8000 &"
echo "  3. streamlit run ui/app.py"
