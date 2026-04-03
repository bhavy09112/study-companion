"""LoRA fine-tuning for Study Companion.

Supports 4-bit QLoRA on consumer GPUs (8GB+ VRAM).
Features: checkpoint resume, sample generation during training, loss logging.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import torch
import yaml
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    TrainerCallback,
    DataCollatorForSeq2Seq,
)


def load_config(config_dir: str = "training/configs") -> dict[str, Any]:
    """Load training and LoRA configs from YAML files."""
    config_path = Path(config_dir)

    with open(config_path / "training_config.yaml") as f:
        train_config = yaml.safe_load(f)
    with open(config_path / "lora_config.yaml") as f:
        lora_config = yaml.safe_load(f)

    return {"training": train_config, "lora": lora_config}


def load_dataset(dataset_path: str, train_split: float = 0.9, seed: int = 42) -> tuple[Dataset, Dataset]:
    """Load and split the training dataset.

    Args:
        dataset_path: Path to JSONL dataset file.
        train_split: Fraction for training (rest is eval).
        seed: Random seed.

    Returns:
        Tuple of (train_dataset, eval_dataset).
    """
    lines = Path(dataset_path).read_text(encoding="utf-8").strip().split("\n")
    examples = [json.loads(line) for line in lines if line.strip()]

    # Format for instruction tuning
    formatted = []
    for ex in examples:
        text = format_instruction(ex["instruction"], ex.get("input", ""), ex["output"])
        formatted.append({"text": text})

    ds = Dataset.from_list(formatted)
    split = ds.train_test_split(test_size=1.0 - train_split, seed=seed)

    return split["train"], split["test"]


def format_instruction(instruction: str, input_text: str, output: str) -> str:
    """Format an example into the Mistral instruction format."""
    if input_text:
        prompt = f"[INST] {instruction}\n\nContext:\n{input_text} [/INST]\n{output}"
    else:
        prompt = f"[INST] {instruction} [/INST]\n{output}"
    return prompt


def tokenize_dataset(dataset: Dataset, tokenizer: Any, max_length: int) -> Dataset:
    """Tokenize a dataset for training."""
    def tokenize_fn(examples: dict) -> dict:
        tokenized = tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_length,
            padding=False,
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    return dataset.map(tokenize_fn, batched=True, remove_columns=dataset.column_names)


class SampleGenerationCallback(TrainerCallback):
    """Generate a sample output every N steps for monitoring."""

    def __init__(self, tokenizer: Any, model: Any, sample_prompt: str, every_n_steps: int = 50):
        self.tokenizer = tokenizer
        self.model = model
        self.sample_prompt = sample_prompt
        self.every_n_steps = every_n_steps

    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step % self.every_n_steps == 0 and state.global_step > 0:
            self._generate_sample(state.global_step)

    def _generate_sample(self, step: int):
        """Generate and print a sample."""
        try:
            self.model.eval()
            inputs = self.tokenizer(self.sample_prompt, return_tensors="pt").to(self.model.device)
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=200,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.9,
                )
            text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            print(f"\n{'='*60}")
            print(f"Sample generation at step {step}:")
            print(f"{'='*60}")
            print(text[:500])
            print(f"{'='*60}\n")
            self.model.train()
        except Exception as e:
            print(f"Sample generation failed at step {step}: {e}")


class LossLoggerCallback(TrainerCallback):
    """Log training and eval loss to a JSON file for plotting."""

    def __init__(self, log_path: str = "training/loss_curve.json"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.losses: list[dict] = []

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs:
            entry = {"step": state.global_step, "epoch": state.epoch}
            if "loss" in logs:
                entry["train_loss"] = logs["loss"]
            if "eval_loss" in logs:
                entry["eval_loss"] = logs["eval_loss"]
            self.losses.append(entry)

            with open(self.log_path, "w") as f:
                json.dump(self.losses, f, indent=2)


def setup_model_and_tokenizer(config: dict) -> tuple[Any, Any]:
    """Load the base model with quantization and tokenizer.

    Args:
        config: Full config dict with training and lora sections.

    Returns:
        Tuple of (model, tokenizer).
    """
    train_cfg = config["training"]
    model_name = train_cfg["base_model"]

    # Quantization config for 4-bit loading
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    print(f"Loading model: {model_name}", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.float16,
    )

    # Prepare for k-bit training
    model = prepare_model_for_kbit_training(model)

    # Apply LoRA
    lora_cfg = config["lora"]
    peft_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        target_modules=lora_cfg["target_modules"],
        lora_dropout=lora_cfg["lora_dropout"],
        bias=lora_cfg["bias"],
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, peft_config)

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Trainable params: {trainable_params:,} / {total_params:,} "
          f"({100 * trainable_params / total_params:.2f}%)", file=sys.stderr)

    return model, tokenizer


def train(
    dataset_path: str,
    config_dir: str = "training/configs",
    resume: bool = True,
) -> str:
    """Run the full training pipeline.

    Args:
        dataset_path: Path to the JSONL training dataset.
        config_dir: Directory containing YAML configs.
        resume: Whether to resume from checkpoint.

    Returns:
        Path to the final checkpoint directory.
    """
    config = load_config(config_dir)
    train_cfg = config["training"]

    # Load model
    model, tokenizer = setup_model_and_tokenizer(config)

    # Load and tokenize dataset
    train_ds, eval_ds = load_dataset(
        dataset_path,
        train_split=train_cfg["train_split"],
        seed=train_cfg["seed"],
    )

    train_ds = tokenize_dataset(train_ds, tokenizer, train_cfg["max_seq_length"])
    eval_ds = tokenize_dataset(eval_ds, tokenizer, train_cfg["max_seq_length"])

    print(f"Train examples: {len(train_ds)}, Eval examples: {len(eval_ds)}", file=sys.stderr)

    # Training arguments
    output_dir = train_cfg["output_dir"]
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=train_cfg["num_epochs"],
        per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
        per_device_eval_batch_size=train_cfg["per_device_eval_batch_size"],
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=train_cfg["learning_rate"],
        lr_scheduler_type=train_cfg["lr_scheduler_type"],
        warmup_ratio=train_cfg["warmup_ratio"],
        weight_decay=train_cfg["weight_decay"],
        max_grad_norm=train_cfg["max_grad_norm"],
        fp16=train_cfg.get("fp16", True),
        bf16=train_cfg.get("bf16", False),
        gradient_checkpointing=train_cfg["gradient_checkpointing"],
        optim=train_cfg.get("optim", "paged_adamw_8bit"),
        save_steps=train_cfg["save_steps"],
        eval_steps=train_cfg["eval_steps"],
        eval_strategy="steps",
        logging_steps=train_cfg["logging_steps"],
        logging_dir=train_cfg.get("logging_dir", "training/logs"),
        save_total_limit=train_cfg.get("save_total_limit", 3),
        load_best_model_at_end=True,
        report_to="none",
        seed=train_cfg["seed"],
    )

    # Callbacks
    sample_prompt = "[INST] Explain photosynthesis in simple terms. [/INST]\n"
    callbacks = [
        SampleGenerationCallback(
            tokenizer, model, sample_prompt,
            every_n_steps=train_cfg.get("sample_generation_steps", 50),
        ),
        LossLoggerCallback(),
    ]

    # Data collator
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        return_tensors="pt",
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=data_collator,
        callbacks=callbacks,
    )

    # Resume from checkpoint if available
    checkpoint = None
    if resume:
        checkpoints = list(Path(output_dir).glob("checkpoint-*"))
        if checkpoints:
            checkpoint = str(max(checkpoints, key=lambda p: int(p.name.split("-")[1])))
            print(f"Resuming from checkpoint: {checkpoint}", file=sys.stderr)

    # Train
    print("Starting training...", file=sys.stderr)
    trainer.train(resume_from_checkpoint=checkpoint)

    # Save final model
    final_dir = f"{output_dir}/final"
    trainer.save_model(final_dir)
    tokenizer.save_pretrained(final_dir)

    print(f"Training complete. Final model saved to {final_dir}", file=sys.stderr)
    return final_dir


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Fine-tune study companion model")
    parser.add_argument("--dataset", "-d", default="data/dataset.jsonl",
                        help="Training dataset JSONL file")
    parser.add_argument("--config-dir", default="training/configs",
                        help="Config directory")
    parser.add_argument("--no-resume", action="store_true",
                        help="Don't resume from checkpoint")
    args = parser.parse_args()

    final_dir = train(
        dataset_path=args.dataset,
        config_dir=args.config_dir,
        resume=not args.no_resume,
    )
    print(f"Model saved to: {final_dir}")


if __name__ == "__main__":
    main()
