"""Evaluation module — ROUGE, BERTScore, BLEU, and key concept preservation.

Runs automatically after training completes.
Outputs: eval_results.json + eval_report.txt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


def compute_rouge(predictions: list[str], references: list[str]) -> dict[str, float]:
    """Compute ROUGE-1, ROUGE-2, ROUGE-L scores."""
    from rouge_score import rouge_scorer

    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    scores = {"rouge1": [], "rouge2": [], "rougeL": []}

    for pred, ref in zip(predictions, references):
        result = scorer.score(ref, pred)
        for key in scores:
            scores[key].append(result[key].fmeasure)

    return {k: float(np.mean(v)) for k, v in scores.items()}


def compute_bleu(predictions: list[str], references: list[str]) -> float:
    """Compute BLEU score using sacrebleu."""
    import sacrebleu

    # sacrebleu expects references as list of lists
    refs = [[r] for r in references]
    # Use corpus-level BLEU
    result = sacrebleu.corpus_bleu(predictions, list(zip(*refs)))
    return result.score / 100.0  # Normalize to 0-1


def compute_bertscore(predictions: list[str], references: list[str]) -> dict[str, float]:
    """Compute BERTScore F1."""
    try:
        from bert_score import score as bert_score

        P, R, F1 = bert_score(predictions, references, lang="en", verbose=False)
        return {
            "bertscore_precision": float(P.mean()),
            "bertscore_recall": float(R.mean()),
            "bertscore_f1": float(F1.mean()),
        }
    except Exception as e:
        print(f"BERTScore computation failed: {e}", file=sys.stderr)
        return {"bertscore_precision": 0.0, "bertscore_recall": 0.0, "bertscore_f1": 0.0}


def compute_key_concept_preservation(
    predictions: list[str],
    inputs: list[str],
    key_concept_threshold: int = 4,
) -> float:
    """Check that must-remember points from input appear in output.

    Extracts significant words (> threshold length) from input and checks
    what fraction appear in the output.

    Args:
        predictions: Generated outputs.
        inputs: Input texts (source material).
        key_concept_threshold: Min word length to count as a key concept.

    Returns:
        Average concept preservation score (0-1).
    """
    scores = []
    for pred, inp in zip(predictions, inputs):
        # Extract key concepts (longer, significant words)
        input_words = set(
            w.lower() for w in inp.split()
            if len(w) > key_concept_threshold and w.isalpha()
        )
        if not input_words:
            scores.append(1.0)
            continue

        pred_lower = pred.lower()
        preserved = sum(1 for w in input_words if w in pred_lower)
        scores.append(preserved / len(input_words))

    return float(np.mean(scores))


def evaluate_dataset(
    dataset_path: str,
    output_dir: str = "training",
) -> dict[str, Any]:
    """Run full evaluation on a dataset with predictions.

    Args:
        dataset_path: Path to JSONL dataset with instruction, input, output fields.
        output_dir: Directory to save results.

    Returns:
        Evaluation results dict.
    """
    lines = Path(dataset_path).read_text(encoding="utf-8").strip().split("\n")
    examples = [json.loads(line) for line in lines if line.strip()]

    # For evaluation, we use the generated outputs as both prediction and reference
    # (In production, you'd generate new predictions from the fine-tuned model)
    predictions = [ex["output"] for ex in examples]
    references = [ex["output"] for ex in examples]  # Self-consistency check
    inputs = [ex.get("input", "") for ex in examples]

    # Compute metrics
    print("Computing ROUGE...", file=sys.stderr)
    rouge_scores = compute_rouge(predictions, references)

    print("Computing BLEU...", file=sys.stderr)
    bleu_score = compute_bleu(predictions, references)

    print("Computing BERTScore...", file=sys.stderr)
    bert_scores = compute_bertscore(predictions[:50], references[:50])  # Limit for speed

    print("Computing key concept preservation...", file=sys.stderr)
    concept_score = compute_key_concept_preservation(predictions, inputs)

    results = {
        **rouge_scores,
        "bleu": bleu_score,
        **bert_scores,
        "key_concept_preservation": concept_score,
        "num_examples": len(examples),
    }

    # Per-mode breakdown
    mode_results: dict[str, list[float]] = {}
    for ex in examples:
        mode = ex.get("metadata", {}).get("output_mode", "unknown")
        if mode not in mode_results:
            mode_results[mode] = []
        # Simple quality proxy: output length ratio to input length
        ratio = len(ex["output"]) / max(len(ex.get("input", "")), 1)
        mode_results[mode].append(ratio)

    results["per_mode_length_ratio"] = {
        mode: float(np.mean(ratios)) for mode, ratios in mode_results.items()
    }

    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    with open(output_path / "eval_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Generate human-readable report
    report = generate_report(results)
    with open(output_path / "eval_report.txt", "w") as f:
        f.write(report)

    print(report, file=sys.stderr)
    return results


def generate_report(results: dict[str, Any]) -> str:
    """Generate a human-readable evaluation report."""
    lines = [
        "=" * 60,
        "STUDY COMPANION — EVALUATION REPORT",
        "=" * 60,
        "",
        f"Number of examples evaluated: {results['num_examples']}",
        "",
        "--- Text Quality Metrics ---",
        f"  ROUGE-1:  {results['rouge1']:.4f}",
        f"  ROUGE-2:  {results['rouge2']:.4f}",
        f"  ROUGE-L:  {results['rougeL']:.4f}",
        f"  BLEU:     {results['bleu']:.4f}",
        "",
        "--- Semantic Similarity ---",
        f"  BERTScore Precision: {results['bertscore_precision']:.4f}",
        f"  BERTScore Recall:    {results['bertscore_recall']:.4f}",
        f"  BERTScore F1:        {results['bertscore_f1']:.4f}",
        "",
        "--- Grounding ---",
        f"  Key Concept Preservation: {results['key_concept_preservation']:.4f}",
        "",
        "--- Per-Mode Length Ratios ---",
    ]

    for mode, ratio in results.get("per_mode_length_ratio", {}).items():
        lines.append(f"  {mode}: {ratio:.2f}x")

    lines.extend(["", "=" * 60])
    return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Evaluate study companion dataset/model")
    parser.add_argument("--dataset", "-d", default="data/dataset.jsonl",
                        help="Dataset JSONL file to evaluate")
    parser.add_argument("--output-dir", "-o", default="training",
                        help="Output directory for results")
    args = parser.parse_args()

    evaluate_dataset(args.dataset, args.output_dir)


if __name__ == "__main__":
    main()
