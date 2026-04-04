# Study Companion AI — Project Plan

## Detected Hardware Summary

| Component | Value |
|-----------|-------|
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU |
| VRAM | 8 GB |
| RAM | 16 GB |
| CPU | 24 cores |
| Disk | 127 GB available |
| CUDA | 13.2 (driver 595.79) |
| Ollama | Installed (mistral, llama3, qwen2.5, deepseek-r1:14b) |
| PyTorch | 2.11.0+cu126 (CUDA enabled) |

## Hardware-Tier Decision Table

```
┌──────────────────┬────────────────────────────┬────────────────┬─────────────────────────┐
│ Detected hardware│ Recommended model           │ Quantization   │ Training feasibility    │
├──────────────────┼────────────────────────────┼────────────────┼─────────────────────────┤
│ CPU only         │ Phi-3-mini-4k-instruct      │ Q4_K_M (GGUF)  │ Inference only locally  │
│ 8 GB VRAM        │ Mistral-7B-Instruct-v0.3    │ Q4_K_M         │ LoRA viable (batch=1)   │
│ 16 GB VRAM       │ Llama-3.1-8B-Instruct       │ Q5_K_M         │ LoRA comfortable        │
│ 24+ GB VRAM      │ Llama-3.1-70B (4-bit)       │ Q4_K_M         │ Full LoRA, larger batch │
│ Cloud A100/H100  │ Llama-3.1-70B or Mistral-22B│ bf16           │ Full fine-tune possible │
└──────────────────┴────────────────────────────┴────────────────┴─────────────────────────┘
```

→ **YOU ARE RUNNING:** RTX 4060 Laptop, 8 GB VRAM, 16 GB RAM, 24 CPU cores
→ **CHOSEN MODEL:** Mistral-7B-Instruct-v0.3 (Q4_K_M via Ollama for inference; 4-bit QLoRA for training)
→ **TRAINING PLAN:** LoRA fine-tuning with batch_size=1, gradient_accumulation=4, 4-bit quantization (bitsandbytes). Ollama `mistral:latest` already available for bootstrapping dataset and fast inference.

## Component Checklist

### Phase 1 — Setup
- [x] PLAN.md created
- [x] Git repo initialized
- [x] Directory structure created
- [x] Dependencies installed (all 6 groups)
- [x] Critical imports verified

### Phase 2 — Data Pipeline
- [x] pipeline/ingest.py — multi-format ingestion
- [x] pipeline/clean.py — text normalization
- [x] pipeline/chunk.py — semantic chunking
- [x] pipeline/generate_dataset.py — instruction-response pairs
- [x] pipeline/embed.py — FAISS + BM25 index
- [x] pipeline/quality.py — dataset quality scorer

### Phase 3 — Training Pipeline
- [x] training/configs/lora_config.yaml
- [x] training/configs/training_config.yaml
- [x] training/train.py — LoRA fine-tuning
- [x] training/evaluate.py — BLEU/ROUGE/BERTScore
- [x] training/export.py — merge + GGUF export

### Phase 4 — Inference Layer
- [x] inference/engine.py — model load + generation
- [x] inference/rag.py — hybrid retrieval
- [x] inference/formatter.py — domain-aware output

### Phase 5 — API
- [x] api/schemas.py — Pydantic models
- [x] api/main.py — FastAPI endpoints

### Phase 6 — Spaced Repetition
- [x] srs/db.py — SQLite schema
- [x] srs/scheduler.py — SM-2 algorithm
- [x] srs/flashcard_export.py — Anki APKG

### Phase 7 — UI
- [x] ui/app.py — Streamlit frontend

### Phase 8 — Scripts & Tests
- [x] scripts/setup_local.sh
- [x] scripts/run_pipeline.sh
- [x] scripts/demo.sh
- [x] tests/conftest.py
- [x] tests/test_ingest.py
- [x] tests/test_chunk.py
- [x] tests/test_rag.py
- [x] tests/test_api.py

### Phase 9 — Documentation
- [x] README.md
- [x] .env.example
- [x] pyproject.toml
- [x] examples/sample_input.pdf

### Phase 10 — End-to-End Verification
- [x] Step 1: Ingest sample PDF
- [x] Step 2: Build FAISS index
- [x] Step 3: Generate dataset
- [x] Step 4: Quality check
- [x] Step 5: API smoke test
- [x] Step 6: UI smoke test
- [x] Step 7: Test suite passes

## Dependency Install Order

1. **GROUP 1 — Core ML:** torch (CUDA), transformers, accelerate, peft, bitsandbytes, datasets
2. **GROUP 2 — RAG:** faiss-cpu, sentence-transformers, rank-bm25, chromadb
3. **GROUP 3 — Ingestion:** pymupdf, pytesseract, python-docx, requests, bs4, youtube-transcript-api, pillow, openai-whisper
4. **GROUP 4 — API/UI:** fastapi, uvicorn, pydantic, streamlit, plotly
5. **GROUP 5 — Eval/Export:** rouge-score, bert-score, sacrebleu, llama-cpp-python
6. **GROUP 6 — SRS/Export:** genanki, pyttsx3

## Estimated Training Feasibility

With 8GB VRAM and 4-bit QLoRA:
- Mistral-7B loads in ~4.5 GB VRAM at 4-bit
- LoRA adapters add ~200 MB
- Batch size 1 with gradient accumulation 4 = effective batch 4
- Training on 1K-5K examples: ~30-60 min per epoch
- **Verdict: VIABLE for local LoRA fine-tuning**

## Known Issues
- PyTorch CUDA wheels required cu126 index (Python 3.14 not supported on cu124)
- `torchaudio` not available for Python 3.14 (not needed for core functionality)
- Template-generated dataset examples have lower quality scores for creative modes (mnemonics, concept_map) — use Ollama generation for production datasets

## Bonus Features
- **Confidence Indicator** — Visual green/yellow/orange/red confidence bar based on retrieval quality
- **Auto-Flashcard Generation** — Extracts definition patterns from study material to create flashcards automatically
- **Study Streak Tracker** — Visual daily streak display to motivate consistent studying
- **Quick Mode Buttons** — One-click rapid switching between study output modes in the UI
- **Topic Mastery Decay** — Recency-weighted mastery scoring that reflects real knowledge retention over time
