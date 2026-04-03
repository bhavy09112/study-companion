"""Domain-aware output formatter.

Detects domain automatically and applies appropriate formatting.
Supports: STEM, Medicine, Law, Programming, Humanities, Languages.
"""
from __future__ import annotations

import re
from typing import Optional


# Domain detection keywords with weights
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "stem": [
        "equation", "formula", "calculate", "theorem", "derivative", "integral",
        "matrix", "vector", "photosynthesis", "molecule", "atom", "electron",
        "energy", "force", "velocity", "acceleration", "mass", "wavelength",
        "frequency", "probability", "statistics", "hypothesis", "experiment",
        "chemical", "reaction", "compound", "element", "periodic", "quantum",
    ],
    "medicine": [
        "patient", "symptom", "diagnosis", "treatment", "drug", "disease",
        "pathology", "clinical", "anatomy", "physiology", "syndrome",
        "prognosis", "dosage", "contraindication", "etiology", "epidemiology",
        "organ", "tissue", "blood", "cardiac", "neural", "respiratory",
    ],
    "law": [
        "court", "statute", "plaintiff", "defendant", "jurisdiction",
        "constitution", "contract", "liability", "precedent", "tort",
        "appeal", "verdict", "legislation", "regulation", "compliance",
        "criminal", "civil", "judge", "jury", "witness", "evidence",
    ],
    "programming": [
        "function", "class", "variable", "algorithm", "api", "database",
        "code", "compile", "runtime", "debug", "syntax", "loop",
        "recursion", "object", "method", "interface", "module", "library",
        "framework", "git", "deploy", "server", "client", "protocol",
    ],
    "humanities": [
        "history", "philosophy", "literature", "culture", "society",
        "argument", "theory", "critique", "narrative", "civilization",
        "revolution", "ideology", "discourse", "ethics", "aesthetics",
        "medieval", "renaissance", "modern", "postmodern", "classical",
    ],
    "languages": [
        "grammar", "vocabulary", "conjugation", "pronunciation", "translation",
        "dialect", "tense", "noun", "verb", "adjective", "adverb",
        "preposition", "syntax", "morphology", "phonetics", "fluency",
    ],
}


def detect_domain(text: str) -> str:
    """Detect the academic domain of the text.

    Args:
        text: Input text to classify.

    Returns:
        Domain string: stem, medicine, law, programming, humanities, languages, or general.
    """
    text_lower = text.lower()
    scores = {domain: 0 for domain in DOMAIN_KEYWORDS}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            count = text_lower.count(kw)
            scores[domain] += count

    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] >= 2 else "general"


def format_output(
    text: str,
    mode: str,
    domain: Optional[str] = None,
    source_chunks: Optional[list[dict]] = None,
) -> str:
    """Format generated output based on domain and mode.

    Args:
        text: Raw generated text.
        mode: Output mode (simple_explanation, key_concepts, etc.).
        domain: Detected or specified domain.
        source_chunks: Source chunks for citation.

    Returns:
        Formatted output string.
    """
    if domain is None:
        domain = detect_domain(text)

    # Apply domain-specific formatting
    text = _apply_domain_format(text, domain)

    # Apply mode-specific formatting
    text = _apply_mode_format(text, mode)

    # Add citations
    if source_chunks:
        text = _add_citations(text, source_chunks)

    return text


def _apply_domain_format(text: str, domain: str) -> str:
    """Apply domain-specific formatting enhancements."""
    formatters = {
        "stem": _format_stem,
        "medicine": _format_medicine,
        "law": _format_law,
        "programming": _format_programming,
        "humanities": _format_humanities,
        "languages": _format_languages,
    }

    formatter = formatters.get(domain)
    if formatter:
        return formatter(text)
    return text


def _format_stem(text: str) -> str:
    """STEM formatting: LaTeX math blocks, formula sections."""
    # Wrap inline math expressions in LaTeX
    text = re.sub(r"(\b\w+\s*=\s*[^,.\n]+)", r"$\1$", text, count=5)

    # Add formula sheet section if formulas detected
    if re.search(r"[=+\-*/^].*\d", text):
        if "formula" not in text.lower() and "equation" not in text.lower():
            text += "\n\n---\n📐 **Key Formulas:** See equations marked with $ symbols above."

    return text


def _format_medicine(text: str) -> str:
    """Medicine formatting: tables for drugs/conditions."""
    # Add clinical note formatting
    if any(kw in text.lower() for kw in ["symptom", "treatment", "diagnosis"]):
        text += "\n\n---\n🏥 **Clinical Note:** Always verify medical information with current guidelines."
    return text


def _format_law(text: str) -> str:
    """Law formatting: case citation style."""
    # Format case references
    text = re.sub(
        r"(\b[A-Z][a-z]+ v\.? [A-Z][a-z]+\b)",
        r"*\1*",
        text,
    )
    return text


def _format_programming(text: str) -> str:
    """Programming formatting: code blocks, Big-O analysis."""
    # Ensure code snippets are in code blocks
    # Already formatted code blocks are preserved
    if "```" not in text and re.search(r"(def |class |function |import |const |let |var )", text):
        lines = text.split("\n")
        in_code = False
        result = []
        for line in lines:
            if re.match(r"^\s*(def |class |function |import |const |let |var |for |if |while )", line):
                if not in_code:
                    result.append("```")
                    in_code = True
                result.append(line)
            else:
                if in_code:
                    result.append("```")
                    in_code = False
                result.append(line)
        if in_code:
            result.append("```")
        text = "\n".join(result)
    return text


def _format_humanities(text: str) -> str:
    """Humanities formatting: timeline, key quotes."""
    # Format dates as timeline entries
    text = re.sub(r"(\d{4})\s*[-–:]\s*", r"**\1** — ", text)
    return text


def _format_languages(text: str) -> str:
    """Languages formatting: vocabulary tables."""
    # Detect word-translation patterns and format as table
    if re.search(r"\w+\s*[-–:]\s*\w+", text) and "translation" in text.lower():
        lines = text.split("\n")
        table_lines = ["| Word | Translation | Example |", "|------|-------------|---------|"]
        has_table = False
        for line in lines:
            m = re.match(r"^\s*(\w+)\s*[-–:]\s*(.+)$", line)
            if m and len(m.group(1)) < 30:
                table_lines.append(f"| {m.group(1)} | {m.group(2)} | — |")
                has_table = True
        if has_table:
            text += "\n\n### Vocabulary Table\n" + "\n".join(table_lines)
    return text


def _apply_mode_format(text: str, mode: str) -> str:
    """Apply mode-specific formatting."""
    headers = {
        "simple_explanation": "## 📖 Simple Explanation",
        "key_concepts": "## 🔑 Key Concepts",
        "exam_critical": "## ⚡ Exam-Critical Points",
        "detailed_explanation": "## 📚 Detailed Explanation",
        "common_mistakes": "## ❌ Common Mistakes & Misconceptions",
        "practice_questions": "## 📝 Practice Questions",
        "revision_sheet": "## 📋 Quick Revision Sheet",
        "mnemonics": "## 🧠 Memory Tricks & Mnemonics",
        "concept_map": "## 🗺️ Concept Map",
    }

    header = headers.get(mode, f"## {mode.replace('_', ' ').title()}")
    return f"{header}\n\n{text}"


def _add_citations(text: str, source_chunks: list[dict]) -> str:
    """Add source citations to the output."""
    if not source_chunks:
        return text

    citations = "\n\n---\n### 📚 Sources\n"
    seen = set()
    for chunk in source_chunks:
        source = chunk.get("source", "unknown")
        page = chunk.get("page", "")
        key = f"{source}:{page}"
        if key not in seen:
            seen.add(key)
            page_str = f", p. {page}" if page else ""
            citations += f"- {source}{page_str}\n"

    return text + citations


# [BONUS FEATURE] Confidence indicator based on retrieval quality
def add_confidence_indicator(text: str, max_score: float) -> str:
    """Add a visual confidence indicator based on retrieval quality.

    [BONUS FEATURE] Helps students understand how reliable the answer is.
    """
    if max_score >= 0.8:
        indicator = "🟢 **High confidence** — Well-supported by your materials"
    elif max_score >= 0.5:
        indicator = "🟡 **Moderate confidence** — Partially supported by your materials"
    elif max_score >= RELEVANCE_THRESHOLD:
        indicator = "🟠 **Low confidence** — Limited support in your materials"
    else:
        indicator = "🔴 **Very low confidence** — Topic may not be in your materials"

    return f"{indicator}\n\n{text}"


# Re-export for convenience
RELEVANCE_THRESHOLD = 0.35


if __name__ == "__main__":
    sample = (
        "Photosynthesis is the process by which plants convert CO2 and H2O into glucose "
        "using light energy. The equation is 6CO2 + 6H2O -> C6H12O6 + 6O2."
    )

    domain = detect_domain(sample)
    print(f"Detected domain: {domain}")

    formatted = format_output(sample, "simple_explanation", domain)
    print(f"\nFormatted output:\n{formatted}")
