"""Dataset quality scorer.

Scores each example on: length ratio, vocabulary richness, answer groundedness.
Flags examples below threshold for human review.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

# Quality thresholds
MIN_LENGTH_RATIO = 0.3       # output should be at least 30% of input length
MAX_LENGTH_RATIO = 10.0      # output shouldn't be more than 10x input length
MIN_VOCAB_RICHNESS = 0.15    # type-token ratio threshold
MIN_GROUNDEDNESS = 0.2       # fraction of output words found in input
OVERALL_THRESHOLD = 0.5      # minimum overall quality score


def score_length_ratio(input_text: str, output_text: str) -> float:
    """Score based on the ratio of output length to input length.

    Returns 1.0 for ratios within the expected range, scaled down outside.
    """
    if not input_text or not output_text:
        return 0.0

    ratio = len(output_text) / max(len(input_text), 1)

    if MIN_LENGTH_RATIO <= ratio <= MAX_LENGTH_RATIO:
        return 1.0
    elif ratio < MIN_LENGTH_RATIO:
        return ratio / MIN_LENGTH_RATIO
    else:
        return max(0.0, 1.0 - (ratio - MAX_LENGTH_RATIO) / MAX_LENGTH_RATIO)


def score_vocab_richness(text: str) -> float:
    """Score vocabulary richness using type-token ratio.

    Higher diversity = better quality output.
    """
    words = text.lower().split()
    if len(words) < 5:
        return 0.0

    # Type-token ratio (unique words / total words)
    ttr = len(set(words)) / len(words)
    return min(1.0, ttr / 0.5)  # Normalize: 0.5 TTR = perfect score


def score_groundedness(input_text: str, output_text: str) -> float:
    """Score how well the output is grounded in the input material.

    Measures overlap of significant words between input and output.
    """
    # Get significant words (longer than 3 chars, not common stopwords)
    stopwords = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can",
        "had", "her", "was", "one", "our", "out", "has", "have", "from",
        "they", "been", "have", "many", "some", "them", "than", "its",
        "over", "such", "that", "this", "with", "will", "each", "make",
        "like", "into", "just", "also", "more", "what", "when", "which",
    }

    input_words = set(
        w for w in input_text.lower().split()
        if len(w) > 3 and w not in stopwords
    )
    output_words = [
        w for w in output_text.lower().split()
        if len(w) > 3 and w not in stopwords
    ]

    if not output_words or not input_words:
        return 0.0

    grounded = sum(1 for w in output_words if w in input_words)
    return grounded / len(output_words)


def score_example(example: dict) -> dict:
    """Score a single dataset example.

    Args:
        example: Dict with instruction, input, output keys.

    Returns:
        Dict with individual scores and overall quality score.
    """
    input_text = example.get("input", "")
    output_text = example.get("output", "")

    length_score = score_length_ratio(input_text, output_text)
    vocab_score = score_vocab_richness(output_text)
    groundedness_score = score_groundedness(input_text, output_text)

    # Weighted overall score
    overall = (
        0.25 * length_score +
        0.25 * vocab_score +
        0.50 * groundedness_score  # Groundedness is most important
    )

    return {
        "length_ratio": round(length_score, 3),
        "vocab_richness": round(vocab_score, 3),
        "groundedness": round(groundedness_score, 3),
        "overall": round(overall, 3),
        "flagged": overall < OVERALL_THRESHOLD,
    }


def generate_quality_report(dataset: list[dict]) -> dict:
    """Generate a quality report for the entire dataset.

    Args:
        dataset: List of dataset examples.

    Returns:
        Quality report dict.
    """
    scores = []
    flagged = []
    mode_scores: dict[str, list[float]] = {}

    for i, example in enumerate(dataset):
        score = score_example(example)
        scores.append(score)

        mode = example.get("metadata", {}).get("output_mode", "unknown")
        if mode not in mode_scores:
            mode_scores[mode] = []
        mode_scores[mode].append(score["overall"])

        if score["flagged"]:
            flagged.append({
                "index": i,
                "instruction": example.get("instruction", "")[:100],
                "scores": score,
            })

    overall_scores = [s["overall"] for s in scores]

    report = {
        "total_examples": len(dataset),
        "flagged_count": len(flagged),
        "flagged_ratio": round(len(flagged) / max(len(dataset), 1), 3),
        "avg_quality": round(sum(overall_scores) / max(len(overall_scores), 1), 3),
        "min_quality": round(min(overall_scores) if overall_scores else 0, 3),
        "max_quality": round(max(overall_scores) if overall_scores else 0, 3),
        "per_mode_avg": {
            mode: round(sum(s) / len(s), 3)
            for mode, s in mode_scores.items()
        },
        "flagged_examples": flagged[:20],  # Top 20 flagged
    }

    return report


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Score dataset quality")
    parser.add_argument("--dataset", "-d", required=True, help="Dataset JSONL file")
    parser.add_argument("--output", "-o", default="data/quality_report.json",
                        help="Output report file")
    parser.add_argument("--threshold", type=float, default=OVERALL_THRESHOLD,
                        help=f"Quality threshold (default: {OVERALL_THRESHOLD})")
    args = parser.parse_args()

    lines = Path(args.dataset).read_text(encoding="utf-8").strip().split("\n")
    dataset = [json.loads(line) for line in lines if line.strip()]

    report = generate_quality_report(dataset)

    # Write report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print(f"Quality Report for {args.dataset}", file=sys.stderr)
    print(f"  Total examples: {report['total_examples']}", file=sys.stderr)
    print(f"  Average quality: {report['avg_quality']}", file=sys.stderr)
    print(f"  Flagged: {report['flagged_count']} ({report['flagged_ratio']*100:.1f}%)", file=sys.stderr)
    print(f"  Report saved to {args.output}", file=sys.stderr)

    for mode, avg in report["per_mode_avg"].items():
        print(f"    {mode}: {avg}", file=sys.stderr)


if __name__ == "__main__":
    main()
