#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="$SCRIPT_DIR/../../models"
mkdir -p "$MODEL_DIR"

wget -O "$MODEL_DIR/Qwen3-VL-2B-Instruct-Q4_K_M.gguf" \
  https://huggingface.co/lmstudio-community/Qwen3-VL-2B-Instruct-GGUF/resolve/main/Qwen3-VL-2B-Instruct-Q4_K_M.gguf