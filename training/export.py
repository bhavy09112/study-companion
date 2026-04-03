"""Export fine-tuned model.

Merge LoRA adapter into base model weights.
Export to GGUF format via llama-cpp-python.
Register with Ollama for local inference.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml


def merge_adapter(
    base_model: str,
    adapter_path: str,
    output_path: str,
) -> str:
    """Merge LoRA adapter weights into the base model.

    Args:
        base_model: HuggingFace model name or path.
        adapter_path: Path to the LoRA adapter directory.
        output_path: Path to save the merged model.

    Returns:
        Path to the merged model.
    """
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    print(f"Loading base model: {base_model}", file=sys.stderr)
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="cpu",  # Merge on CPU to save VRAM
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model)

    print(f"Loading adapter from: {adapter_path}", file=sys.stderr)
    model = PeftModel.from_pretrained(model, adapter_path)

    print("Merging adapter weights...", file=sys.stderr)
    model = model.merge_and_unload()

    # Save merged model
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output)
    tokenizer.save_pretrained(output)

    print(f"Merged model saved to: {output}", file=sys.stderr)
    return str(output)


def convert_to_gguf(
    model_path: str,
    output_path: str,
    quantization: str = "Q4_K_M",
) -> str:
    """Convert a HuggingFace model to GGUF format.

    This requires llama-cpp-python or the llama.cpp convert script.

    Args:
        model_path: Path to the merged HF model.
        output_path: Output GGUF file path.
        quantization: Quantization type (Q4_K_M, Q5_K_M, Q8_0, etc.).

    Returns:
        Path to the GGUF file.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Try using llama-cpp-python's convert script
    try:
        # First convert to GGUF (f16)
        f16_path = str(output).replace(".gguf", "-f16.gguf")

        # Try the python conversion path
        result = subprocess.run(
            [
                sys.executable, "-m", "llama_cpp.convert",
                "--outfile", f16_path,
                "--outtype", "f16",
                model_path,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Quantize
            subprocess.run(
                [
                    sys.executable, "-m", "llama_cpp.quantize",
                    f16_path,
                    str(output),
                    quantization,
                ],
                check=True,
            )
            print(f"GGUF exported: {output} ({quantization})", file=sys.stderr)
            return str(output)
    except Exception as e:
        print(f"llama-cpp-python conversion failed: {e}", file=sys.stderr)

    # Fallback: create a Modelfile for Ollama that points to the HF model
    print("GGUF conversion not available. Creating Ollama Modelfile instead.", file=sys.stderr)
    modelfile_path = output.parent / "Modelfile"
    with open(modelfile_path, "w") as f:
        f.write(f'FROM {model_path}\n')
        f.write('PARAMETER temperature 0.7\n')
        f.write('PARAMETER top_p 0.9\n')
        f.write('PARAMETER stop "[INST]"\n')
        f.write('PARAMETER stop "[/INST]"\n')
        f.write('SYSTEM "You are a helpful study assistant. Provide clear, accurate, '
                'and well-structured study materials."\n')

    print(f"Modelfile created at {modelfile_path}", file=sys.stderr)
    return str(modelfile_path)


def register_with_ollama(
    model_path: str,
    model_name: str = "study-companion",
) -> bool:
    """Register the model with Ollama for serving.

    Args:
        model_path: Path to GGUF file or Modelfile.
        model_name: Name to register in Ollama.

    Returns:
        True if successful.
    """
    modelfile_path = model_path
    if model_path.endswith(".gguf"):
        # Create a Modelfile
        modelfile_dir = Path(model_path).parent
        modelfile_path = str(modelfile_dir / "Modelfile")
        with open(modelfile_path, "w") as f:
            f.write(f'FROM {model_path}\n')
            f.write('PARAMETER temperature 0.7\n')
            f.write('PARAMETER top_p 0.9\n')
            f.write('SYSTEM "You are a helpful study assistant."\n')

    try:
        result = subprocess.run(
            ["ollama", "create", model_name, "-f", modelfile_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            print(f"Model registered with Ollama as '{model_name}'", file=sys.stderr)
            return True
        else:
            print(f"Ollama registration failed: {result.stderr}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Ollama not available: {e}", file=sys.stderr)
        return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Export fine-tuned model")
    parser.add_argument("--adapter", "-a", default="training/checkpoints/final",
                        help="Path to LoRA adapter directory")
    parser.add_argument("--config-dir", default="training/configs",
                        help="Config directory")
    parser.add_argument("--output-dir", "-o", default="training/exports",
                        help="Export output directory")
    parser.add_argument("--quantization", "-q", default="Q4_K_M",
                        help="GGUF quantization type")
    parser.add_argument("--skip-merge", action="store_true",
                        help="Skip merge step (use pre-merged model)")
    parser.add_argument("--skip-gguf", action="store_true",
                        help="Skip GGUF conversion")
    parser.add_argument("--ollama-name", default="study-companion",
                        help="Ollama model name")
    args = parser.parse_args()

    # Load config to get base model name
    with open(Path(args.config_dir) / "training_config.yaml") as f:
        config = yaml.safe_load(f)

    base_model = config["base_model"]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Merge adapter
    if not args.skip_merge:
        merged_path = str(output_dir / "merged")
        try:
            merge_adapter(base_model, args.adapter, merged_path)
        except Exception as e:
            print(f"Merge failed (adapter may not exist yet): {e}", file=sys.stderr)
            print("Skipping export — run training first.", file=sys.stderr)
            return
    else:
        merged_path = args.adapter

    # Step 2: Convert to GGUF
    if not args.skip_gguf:
        gguf_path = str(output_dir / f"study-companion-{args.quantization}.gguf")
        result_path = convert_to_gguf(merged_path, gguf_path, args.quantization)
    else:
        result_path = merged_path

    # Step 3: Register with Ollama
    register_with_ollama(result_path, args.ollama_name)

    print(f"Export complete. Files in {output_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
