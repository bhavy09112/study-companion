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
| PyTorch | 2.10.0 (CPU-only — needs CUDA reinstall) |

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
- [ ] PLAN.md created
- [ ] Git repo initialized
- [ ] Directory structure created
- [ ] Dependencies installed (all 6 groups)
- [ ] Critical imports verified

### Phase 2 — Data Pipeline
- [ ] pipeline/ingest.py — multi-format ingestion
- [ ] pipeline/clean.py — text normalization
- [ ] pipeline/chunk.py — semantic chunking
- [ ] pipeline/generate_dataset.py — instruction-response pairs
- [ ] pipeline/embed.py — FAISS + BM25 index
- [ ] pipeline/quality.py — dataset quality scorer

### Phase 3 — Training Pipeline
- [ ] training/configs/lora_config.yaml
- [ ] training/configs/training_config.yaml
- [ ] training/train.py — LoRA fine-tuning
- [ ] training/evaluate.py — BLEU/ROUGE/BERTScore
- [ ] training/export.py — merge + GGUF export

### Phase 4 — Inference Layer
- [ ] inference/engine.py — model load + generation
- [ ] inference/rag.py — hybrid retrieval
- [ ] inference/formatter.py — domain-aware output

### Phase 5 — API
- [ ] api/schemas.py — Pydantic models
- [ ] api/main.py — FastAPI endpoints

### Phase 6 — Spaced Repetition
- [ ] srs/db.py — SQLite schema
- [ ] srs/scheduler.py — SM-2 algorithm
- [ ] srs/flashcard_export.py — Anki APKG

### Phase 7 — UI
- [ ] ui/app.py — Streamlit frontend

### Phase 8 — Scripts & Tests
- [ ] scripts/setup_local.sh
- [ ] scripts/run_pipeline.sh
- [ ] scripts/demo.sh
- [ ] tests/conftest.py
- [ ] tests/test_ingest.py
- [ ] tests/test_chunk.py
- [ ] tests/test_rag.py
- [ ] tests/test_api.py

### Phase 9 — Documentation
- [ ] README.md
- [ ] .env.example
- [ ] pyproject.toml
- [ ] examples/sample_input.pdf

### Phase 10 — End-to-End Verification
- [ ] Step 1: Ingest sample PDF
- [ ] Step 2: Build FAISS index
- [ ] Step 3: Generate dataset
- [ ] Step 4: Quality check
- [ ] Step 5: API smoke test
- [ ] Step 6: UI smoke test
- [ ] Step 7: Test suite passes

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
(populated during build)

## Bonus Features
(populated during build)
