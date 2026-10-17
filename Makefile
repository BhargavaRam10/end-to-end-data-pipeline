.PHONY: setup data ingest test clean

setup:
	pip install -r requirements.txt
	cp -n .env.example .env || true

data:
	python data/generate_synthetic_data.py

ingest:
	python ingestion/run_bronze_load.py

test:
	python -m pytest tests/ -q

clean:
	rm -rf data/bronze __pycache__ .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
