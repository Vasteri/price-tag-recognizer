my_path="$(dirname $0)/.."

./$my_path/src/.venv/bin/uvicorn main:app --app-dir $my_path/src/ --host 0.0.0.0 --port 8000