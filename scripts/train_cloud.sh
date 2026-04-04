#!/usr/bin/env bash
# Study Companion AI — Cloud Training Launch Script
# For use with Modal, RunPod, or similar GPU cloud providers.
#
# Usage: bash scripts/train_cloud.sh [dataset_path]

set -e

DATASET="${1:-data/dataset.jsonl}"

echo "=== Study Companion — Cloud Training ==="
echo "Dataset: $DATASET"
echo "Config dir: training/configs/"

# Verify dataset exists
if [ ! -f "$DATASET" ]; then
    echo "Error: Dataset not found at $DATASET"
    echo "Run the pipeline first: bash scripts/run_pipeline.sh <input> --with-dataset"
    exit 1
fi

echo "Dataset size: $(wc -l < "$DATASET") examples"

# Launch training
echo ""
echo "Starting training..."
python training/train.py --dataset "$DATASET"

# Run evaluation
echo ""
echo "Running evaluation..."
python training/evaluate.py --dataset "$DATASET"

# Export (optional)
echo ""
echo "Training complete. To export:"
echo "  python training/export.py"
