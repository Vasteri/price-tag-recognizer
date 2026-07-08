$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelDir = Join-Path $scriptDir "..\..\models"
New-Item -ItemType Directory -Force -Path $modelDir

$url = "https://huggingface.co/lmstudio-community/Qwen3-VL-2B-Instruct-GGUF/resolve/main/Qwen3-VL-2B-Instruct-Q4_K_M.gguf"
$outFile = Join-Path $modelDir "Qwen3-VL-2B-Instruct-Q4_K_M.gguf"

Invoke-WebRequest -Uri $url -OutFile $outFile