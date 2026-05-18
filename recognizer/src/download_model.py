from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id="openfoodfacts/price-tag-detection",
    filename="weights/best.pt",
    cache_dir="/hf_cache",
    resume_download=True
)
print("Скачано в кеш")