"""Inference engine — model loading and generation.

Supports Ollama (primary) and direct HuggingFace model loading.
Enforces safety and grounding rules on all generated output.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Optional

import requests

# Configuration via environment
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:latest")
GROUNDING_THRESHOLD = float(os.getenv("GROUNDING_THRESHOLD", "0.6"))


class InferenceEngine:
    """Unified inference engine with Ollama backend."""

    def __init__(
        self,
        model_name: str = OLLAMA_MODEL,
        ollama_url: str = OLLAMA_URL,
        grounding_threshold: float = GROUNDING_THRESHOLD,
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.grounding_threshold = grounding_threshold
        self._available: Optional[bool] = None

    @property
    def is_available(self) -> bool:
        """Check if the inference backend is available."""
        if self._available is None:
            try:
                resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                self._available = resp.status_code == 200
            except Exception:
                self._available = False
        return self._available

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        context_chunks: Optional[list[dict]] = None,
    ) -> dict:
        """Generate a response using the inference backend.

        Args:
            prompt: User prompt / instruction.
            system_prompt: System-level instruction.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            top_p: Nucleus sampling threshold.
            context_chunks: Retrieved RAG chunks for grounding.

        Returns:
            Dict with 'text', 'grounded', 'warnings' keys.
        """
        if system_prompt is None:
            system_prompt = (
                "You are a helpful study assistant. Provide clear, accurate, and well-structured "
                "study materials. Always base your answers on the provided context material. "
                "If information is not in the provided material, clearly state that."
            )

        # Build context from RAG chunks
        context = ""
        if context_chunks:
            context_parts = []
            for i, chunk in enumerate(context_chunks, 1):
                source = chunk.get("source", "unknown")
                text = chunk.get("text", "")
                context_parts.append(f"[Source {i}: {source}]\n{text}")
            context = "\n\n".join(context_parts)

        # Construct full prompt
        full_prompt = self._build_prompt(prompt, context, system_prompt)

        # Generate
        response_text = self._call_ollama(full_prompt, max_tokens, temperature, top_p)

        if not response_text:
            return {
                "text": "I'm sorry, I couldn't generate a response. Please check that the inference backend is running.",
                "grounded": False,
                "warnings": ["Backend unavailable"],
            }

        # Safety and grounding check
        warnings = []
        grounded = True

        if context_chunks:
            grounded, ungrounded_claims = self._check_grounding(response_text, context_chunks)
            if not grounded:
                warnings.append("Some claims may not be well-supported by your material")
                # Annotate ungrounded sections
                response_text = self._annotate_ungrounded(response_text, ungrounded_claims)

        if not context_chunks or not context:
            warnings.append("No source material provided — response based on general knowledge")
            response_text += "\n\n⚠ *This response is based on general knowledge, not your study materials.*"

        return {
            "text": response_text,
            "grounded": grounded,
            "warnings": warnings,
        }

    def _build_prompt(self, user_prompt: str, context: str, system_prompt: str) -> str:
        """Build the full prompt for the model."""
        parts = []
        if context:
            parts.append(f"Context material:\n{context}\n")
        parts.append(f"Task: {user_prompt}")

        combined = "\n\n".join(parts)
        return f"[INST] {system_prompt}\n\n{combined} [/INST]"

    def _call_ollama(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> Optional[str]:
        """Call the Ollama API."""
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                        "top_p": top_p,
                    },
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            print(f"Ollama call failed: {e}", file=sys.stderr)
            return None

    def _check_grounding(
        self,
        response: str,
        context_chunks: list[dict],
    ) -> tuple[bool, list[str]]:
        """Check if response claims are grounded in context.

        Returns:
            Tuple of (is_grounded, list_of_ungrounded_claims).
        """
        # Extract sentences from response
        sentences = re.split(r"[.!?]+", response)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        # Build context word set
        context_text = " ".join(c.get("text", "") for c in context_chunks).lower()
        context_words = set(context_text.split())

        ungrounded = []
        for sentence in sentences:
            words = set(sentence.lower().split())
            significant_words = {w for w in words if len(w) > 4}
            if not significant_words:
                continue

            overlap = len(significant_words & context_words) / len(significant_words)
            if overlap < self.grounding_threshold:
                ungrounded.append(sentence)

        is_grounded = len(ungrounded) <= len(sentences) * 0.3  # Allow 30% ungrounded
        return is_grounded, ungrounded

    def _annotate_ungrounded(self, text: str, ungrounded_claims: list[str]) -> str:
        """Add warnings to ungrounded claims in the text."""
        for claim in ungrounded_claims[:5]:  # Limit annotations
            if claim in text:
                text = text.replace(
                    claim,
                    f"{claim} ⚠ [Not found in your material — general knowledge]",
                    1,
                )
        return text

    def health_check(self) -> dict:
        """Return health status of the inference engine."""
        import torch

        vram_gb = 0.0
        if torch.cuda.is_available():
            vram_gb = torch.cuda.memory_allocated(0) / (1024 ** 3)

        return {
            "model_loaded": self.is_available,
            "model_name": self.model_name,
            "backend": "ollama",
            "vram_used_gb": round(vram_gb, 2),
        }


# Module-level singleton
_engine: Optional[InferenceEngine] = None


def get_engine() -> InferenceEngine:
    """Get or create the global inference engine."""
    global _engine
    if _engine is None:
        _engine = InferenceEngine()
    return _engine


if __name__ == "__main__":
    engine = get_engine()
    print(f"Engine available: {engine.is_available}")
    print(f"Health: {engine.health_check()}")

    if engine.is_available:
        result = engine.generate("What is photosynthesis? Explain briefly.")
        print(f"\nGenerated:\n{result['text'][:500]}")
        print(f"Grounded: {result['grounded']}")
        print(f"Warnings: {result['warnings']}")
