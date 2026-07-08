$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelDir = Join-Path $scriptDir "..\..\models"
New-Item -ItemType Directory -Force -Path $modelDir

#$url = "https://huggingface.co/lmstudio-community/Qwen3-VL-2B-Instruct-GGUF/resolve/main/Qwen3-VL-2B-Instruct-Q4_K_M.gguf"
#$outFile = Join-Path $modelDir "Qwen3-VL-2B-Instruct-Q4_K_M.gguf"

$url2 = "https://huggingface.co/lmstudio-community/Qwen3-VL-2B-Instruct-GGUF/resolve/main/mmproj-Qwen3-VL-2B-Instruct-F16.gguf"
$outFile2 = Join-Path $modelDir "mmproj-Qwen3-VL-2B-Instruct-F16.gguf"

#Invoke-WebRequest -Uri $url -OutFile $outFile
Invoke-WebRequest -Uri $url2 -OutFile $outFile2
