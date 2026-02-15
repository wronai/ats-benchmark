.PHONY: run install

install:
	pip install -r requirements.txt

run: install
	cd /workspace && python -m benchmarks.baseline.benchmark
