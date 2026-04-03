"""Instruction-response pair generation for fine-tuning.

For each chunk, generates instruction-response pairs covering all study output modes.
Uses Ollama (local model) to bootstrap initial examples.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Optional

import requests

# Ollama API endpoint
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral:latest"

# All output modes
OUTPUT_MODES = [
    "simple_explanation",
    "key_concepts",
    "exam_critical",
    "detailed_explanation",
    "common_mistakes",
    "practice_questions",
    "revision_sheet",
    "mnemonics",
    "concept_map",
]

# Prompt templates per mode
PROMPTS: dict[str, str] = {
    "simple_explanation": (
        "Explain the following topic in simple terms that a 15-year-old could understand. "
        "Use analogies and everyday language.\n\nTopic:\n{chunk}"
    ),
    "key_concepts": (
        "Extract and define the key concepts from the following material. "
        "Format as a numbered list: concept name followed by a clear definition.\n\nMaterial:\n{chunk}"
    ),
    "exam_critical": (
        "Identify the must-remember, exam-critical points from this material. "
        "These are facts, formulas, or definitions that are most likely to appear on an exam.\n\nMaterial:\n{chunk}"
    ),
    "detailed_explanation": (
        "Provide a detailed explanation of the following material with worked examples. "
        "Include step-by-step reasoning and numerical examples where applicable.\n\nMaterial:\n{chunk}"
    ),
    "common_mistakes": (
        "List the most common mistakes and misconceptions students have about the following topic. "
        "For each mistake, explain why it's wrong and what the correct understanding is.\n\nTopic:\n{chunk}"
    ),
    "practice_questions": (
        "Generate practice questions based on the following material. Include:\n"
        "- 3 multiple choice questions (with 4 options each and the correct answer marked)\n"
        "- 2 short-answer questions with model answers\n"
        "- 1 problem-solving question with a worked solution\n\nMaterial:\n{chunk}"
    ),
    "revision_sheet": (
        "Create a concise one-page revision sheet for the following topic. "
        "Include key formulas, definitions, diagrams described in text, and quick-reference lists.\n\nTopic:\n{chunk}"
    ),
    "mnemonics": (
        "Create memory tricks, mnemonics, and analogies to help remember the key information "
        "from the following material. Make them creative and memorable.\n\nMaterial:\n{chunk}"
    ),
    "concept_map": (
        "Create a concept map for the following material using Mermaid diagram syntax. "
        "Show relationships between key concepts with labeled arrows.\n\nMaterial:\n{chunk}"
    ),
}

# Difficulty levels
DIFFICULTIES = ["beginner", "intermediate", "advanced"]

# Instruction variations per mode for augmentation
INSTRUCTION_VARIANTS: dict[str, list[str]] = {
    "simple_explanation": [
        "Explain {topic} in simple terms.",
        "Give me an ELI15 explanation of {topic}.",
        "Break down {topic} for a beginner.",
        "What is {topic}? Explain simply.",
    ],
    "key_concepts": [
        "What are the key concepts in {topic}?",
        "List and define the main ideas in {topic}.",
        "Extract the core concepts from {topic}.",
    ],
    "exam_critical": [
        "What are the exam-critical points for {topic}?",
        "What must I memorize about {topic}?",
        "List the most testable facts about {topic}.",
    ],
    "detailed_explanation": [
        "Explain {topic} in detail with examples.",
        "Give a thorough explanation of {topic}.",
        "Deep dive into {topic} with worked examples.",
    ],
    "common_mistakes": [
        "What mistakes do students commonly make about {topic}?",
        "List misconceptions about {topic}.",
        "What do people get wrong about {topic}?",
    ],
    "practice_questions": [
        "Generate practice questions on {topic}.",
        "Create a quiz about {topic}.",
        "Give me exam-style questions on {topic}.",
    ],
    "revision_sheet": [
        "Create a revision sheet for {topic}.",
        "Summarize {topic} for quick revision.",
        "Make a cheat sheet for {topic}.",
    ],
    "mnemonics": [
        "Create mnemonics for {topic}.",
        "Give me memory tricks for {topic}.",
        "How can I remember the key points of {topic}?",
    ],
    "concept_map": [
        "Draw a concept map for {topic}.",
        "Show how concepts in {topic} relate to each other.",
        "Create a visual overview of {topic}.",
    ],
}


def _extract_topic(chunk_text: str) -> str:
    """Extract a topic name from chunk text (first line or first sentence)."""
    first_line = chunk_text.strip().split("\n")[0].strip()
    # Clean up: remove numbering, bullet points
    first_line = first_line.lstrip("0123456789.-#*) ").strip()
    if len(first_line) > 100:
        first_line = first_line[:100] + "..."
    return first_line or "this topic"


def _detect_domain(text: str) -> str:
    """Simple domain detection from text content."""
    text_lower = text.lower()
    domain_keywords = {
        "stem": ["equation", "formula", "calculate", "theorem", "variable", "function",
                 "derivative", "integral", "matrix", "vector", "photosynthesis",
                 "molecule", "atom", "electron", "energy", "force", "velocity"],
        "medicine": ["patient", "symptom", "diagnosis", "treatment", "drug", "disease",
                     "pathology", "clinical", "anatomy", "physiology"],
        "law": ["court", "statute", "plaintiff", "defendant", "jurisdiction",
                "constitution", "contract", "liability", "precedent"],
        "programming": ["function", "class", "variable", "algorithm", "api", "database",
                        "code", "compile", "runtime", "debug", "syntax"],
        "humanities": ["history", "philosophy", "literature", "culture", "society",
                       "argument", "theory", "critique", "narrative"],
        "languages": ["grammar", "vocabulary", "conjugation", "pronunciation",
                      "translation", "dialect", "tense"],
    }

    scores = {domain: 0 for domain in domain_keywords}
    for domain, keywords in domain_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                scores[domain] += 1

    best_domain = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best_domain if scores[best_domain] > 0 else "general"


def generate_with_ollama(prompt: str, model: str = OLLAMA_MODEL) -> Optional[str]:
    """Generate text using Ollama API.

    Args:
        prompt: The prompt to send.
        model: Ollama model name.

    Returns:
        Generated text or None on failure.
    """
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"Ollama generation failed: {e}", file=sys.stderr)
        return None


def generate_template_response(chunk_text: str, mode: str) -> str:
    """Generate a template-based response when Ollama is not available.

    This provides a structured skeleton that can be improved during fine-tuning.
    """
    topic = _extract_topic(chunk_text)

    templates = {
        "simple_explanation": f"Here's a simple explanation of {topic}:\n\n{chunk_text[:500]}",
        "key_concepts": f"Key concepts in {topic}:\n\n1. " + "\n2. ".join(
            line.strip() for line in chunk_text.split("\n")
            if line.strip() and len(line.strip()) > 10
        )[:500],
        "exam_critical": f"Must-remember points for {topic}:\n\n" + "\n".join(
            f"• {line.strip()}" for line in chunk_text.split("\n")
            if line.strip() and len(line.strip()) > 10
        )[:500],
        "detailed_explanation": f"Detailed explanation of {topic}:\n\n{chunk_text}",
        "common_mistakes": f"Common mistakes about {topic}:\n\n1. Confusing related concepts\n2. Forgetting key details\n3. Misapplying formulas or rules",
        "practice_questions": f"Practice questions on {topic}:\n\nQ1 (MCQ): Based on the material, which of the following is correct?\nA) Option A\nB) Option B\nC) Option C\nD) Option D\nAnswer: See material for details.",
        "revision_sheet": f"Quick Revision — {topic}\n\n" + chunk_text[:400],
        "mnemonics": f"Memory tricks for {topic}:\n\nCreate an acronym from the key points.",
        "concept_map": f"```mermaid\ngraph TD\n    A[{topic}] --> B[Concept 1]\n    A --> C[Concept 2]\n    B --> D[Detail]\n```",
    }

    return templates.get(mode, chunk_text[:500])


def generate_dataset_for_chunk(
    chunk: dict,
    use_ollama: bool = True,
    model: str = OLLAMA_MODEL,
) -> list[dict]:
    """Generate instruction-response pairs for a single chunk.

    Args:
        chunk: Chunk dict with text, chunk_id, source keys.
        use_ollama: Whether to use Ollama for generation.
        model: Ollama model name.

    Returns:
        List of dataset examples.
    """
    chunk_text = chunk["text"]
    topic = _extract_topic(chunk_text)
    domain = _detect_domain(chunk_text)
    source = chunk.get("source", "unknown")

    examples = []
    for mode in OUTPUT_MODES:
        prompt = PROMPTS[mode].format(chunk=chunk_text)

        if use_ollama:
            response = generate_with_ollama(prompt, model=model)
        else:
            response = None

        if not response:
            response = generate_template_response(chunk_text, mode)

        # Pick a random instruction variant
        variants = INSTRUCTION_VARIANTS.get(mode, [f"Help me study {topic}"])
        instruction = random.choice(variants).format(topic=topic)
        difficulty = random.choice(DIFFICULTIES)

        examples.append({
            "instruction": instruction,
            "input": chunk_text,
            "output": response,
            "metadata": {
                "source": source,
                "domain": domain,
                "output_mode": mode,
                "difficulty": difficulty,
                "chunk_id": chunk.get("chunk_id", ""),
            },
        })

    return examples


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate training dataset")
    parser.add_argument("--input", "-i", required=True, help="Input JSONL with chunks")
    parser.add_argument("--output", "-o", required=True, help="Output JSONL file")
    parser.add_argument("--no-ollama", action="store_true",
                        help="Skip Ollama generation, use templates only")
    parser.add_argument("--model", default=OLLAMA_MODEL, help=f"Ollama model (default: {OLLAMA_MODEL})")
    parser.add_argument("--max-chunks", type=int, default=None,
                        help="Max number of chunks to process")
    args = parser.parse_args()

    lines = Path(args.input).read_text(encoding="utf-8").strip().split("\n")
    chunks = [json.loads(line) for line in lines if line.strip()]

    if args.max_chunks:
        chunks = chunks[:args.max_chunks]

    # Check Ollama availability
    use_ollama = not args.no_ollama
    if use_ollama:
        try:
            requests.get("http://localhost:11434/api/tags", timeout=5)
            print(f"Ollama available, using model: {args.model}", file=sys.stderr)
        except Exception:
            print("Ollama not reachable, falling back to templates", file=sys.stderr)
            use_ollama = False

    all_examples = []
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}...", file=sys.stderr)
        examples = generate_dataset_for_chunk(chunk, use_ollama=use_ollama, model=args.model)
        all_examples.extend(examples)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"Generated {len(all_examples)} examples from {len(chunks)} chunks", file=sys.stderr)


if __name__ == "__main__":
    main()
