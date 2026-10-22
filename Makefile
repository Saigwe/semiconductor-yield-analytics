PY ?= python
DB ?= warehouse/bt2.duckdb
DBT = cd dbt && BT2_DUCKDB_PATH=../$(DB) dbt

.PHONY: all fixture-all download bronze bronze-fixture context dbt anomaly eval-self-check clean

all: download bronze context dbt anomaly            ## real SECOM data
fixture-all: bronze-fixture context dbt eval-self-check  ## small synthetic fixture, no download (CI)

download:
	$(PY) ingestion/download_secom.py --out-dir data/raw

bronze:
	$(PY) ingestion/build_bronze.py --raw-dir data/raw --db $(DB)

bronze-fixture:
	$(PY) tests/fixtures/make_fixture.py --out-dir data/raw_fixture
	$(PY) ingestion/build_bronze.py --raw-dir data/raw_fixture --db $(DB)

context:
	$(PY) ingestion/generate_context.py --db $(DB)

dbt:
	$(DBT) build --profiles-dir .

anomaly:
	$(PY) analysis/anomaly_detection.py --db $(DB)

eval-self-check:
	$(PY) nl2sql/run_eval.py --db $(DB) --self-check

clean:
	rm -rf warehouse data/raw_fixture dbt/target dbt/logs
