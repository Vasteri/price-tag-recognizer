$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelDir = Join-Path $scriptDir "..\..\models"
New-Item -ItemType Directory -Force -Path $modelDir
$ProgressPreference = 'SilentlyContinue'

$url = "https://huggingface.co/lmstudio-community/Qwen3-VL-2B-Instruct-GGUF/resolve/main/Qwen3-VL-2B-Instruct-Q4_K_M.gguf"
$outFile = Join-Path $modelDir "Qwen3-VL-2B-Instruct-Q4_K_M.gguf"

$url2 = "https://huggingface.co/lmstudio-community/Qwen3-VL-2B-Instruct-GGUF/resolve/main/mmproj-Qwen3-VL-2B-Instruct-F16.gguf"
$outFile2 = Join-Path $modelDir "mmproj-Qwen3-VL-2B-Instruct-F16.gguf"

$url3 = "https://huggingface.co/openfoodfacts/price-tag-detection/resolve/main/weights/best.pt"
$outFile3 = Join-Path $modelDir "yolo-price-tag-detection.pt"

Write-Host "Downloading Qwen3-VL-2B..."
Invoke-WebRequest -Uri $url -OutFile $outFile
Write-Host "Downloading mmproj-Qwen3-VL-2B..."
Invoke-WebRequest -Uri $url2 -OutFile $outFile2
Write-Host "Downloading yolo..."
Invoke-WebRequest -Uri $url3 -OutFile $outFile3