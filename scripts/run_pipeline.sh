#!/usr/bin/env bash
# Study Companion AI — Full Pipeline Runner
# Usage: bash scripts/run_pipeline.sh <input_file_or_url>

set -e

INPUT="${1:?Usage: run_pipeline.sh <input_file_or_url>}"

echo "=== Study Companion — Running Pipeline ==="
echo "Input: $INPUT"

# Step 1: Ingest
echo ""
echo "[1/5] Ingesting..."
python pipeline/ingest.py "$INPUT" -o data/processed/chunks_raw.jsonl
echo "  Raw documents: $(wc -l < data/processed/chunks_raw.jsonl)"

# Step 2: Clean
echo "[2/5] Cleaning..."
python pipeline/clean.py data/processed/chunks_raw.jsonl > data/processed/chunks_clean.jsonl
echo "  Cleaned documents: $(wc -l < data/processed/chunks_clean.jsonl)"

# Step 3: Chunk
echo "[3/5] Chunking..."
python pipeline/chunk.py data/processed/chunks_clean.jsonl -o data/processed/chunks.jsonl
echo "  Chunks: $(wc -l < data/processed/chunks.jsonl)"

# Step 4: Embed
echo "[4/5] Building index..."
python pipeline/embed.py --input data/processed/chunks.jsonl
echo "  FAISS + BM25 indices built"

# Step 5: Generate dataset (optional — for training)
if [ "${2}" = "--with-dataset" ]; then
    echo "[5/5] Generating training dataset..."
    python pipeline/generate_dataset.py --input data/processed/chunks.jsonl --output data/dataset.jsonl
    echo "  Dataset examples: $(wc -l < data/dataset.jsonl)"

    echo "Running quality check..."
    python pipeline/quality.py --dataset data/dataset.jsonl
else
    echo "[5/5] Skipping dataset generation (add --with-dataset flag to include)"
fi

echo ""
echo "=== Pipeline Complete ==="
echo "Index ready at: data/embeddings/"
echo "Start the API: uvicorn api.main:app --port 8000"
