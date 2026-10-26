PY ?= python
DB ?= warehouse/bt2.duckdb
RESULTS ?= results
DBT_BIN ?= dbt
DBT = cd dbt && BT2_DUCKDB_PATH=../$(DB) $(DBT_BIN)

.PHONY: all fixture-all download bronze bronze-fixture context dbt analysis eval agent-eval report-data test clean

all: download bronze context dbt analysis eval report-data   ## real SECOM data

fixture-all:   ## small synthetic fixture, no download (CI): same pipeline, results to data/fixture/results
	$(PY) tests/fixtures/make_fixture.py --out-dir data/raw_fixture
	$(PY) ingestion/build_bronze.py --raw-dir data/raw_fixture --db warehouse/fixture.duckdb
	$(MAKE) context dbt analysis eval test DB=warehouse/fixture.duckdb RESULTS=data/fixture/results

download:
	$(PY) ingestion/download_secom.py --out-dir data/raw

bronze:
	$(PY) ingestion/build_bronze.py --raw-dir data/raw --db $(DB)

context:
	$(PY) ingestion/generate_context.py --db $(DB)

dbt:
	$(DBT) deps --profiles-dir . && $(DBT) build --profiles-dir .

analysis:   ## wafer ranking on a time split, and multiple-testing checks on the sensor ranking
	$(PY) analysis/anomaly_detection.py --db $(DB) --out $(RESULTS)
	$(PY) analysis/fail_signal_significance.py --db $(DB) --out $(RESULTS)

eval:       ## guardrail adversarial suite + benchmark self-check (no API call)
	cd nl2sql && $(PY) run_eval.py --db ../$(DB) --out ../$(RESULTS) --guardrail --self-check

agent-eval: ## the Claude agent on the benchmark (needs Anthropic credentials)
	cd nl2sql && $(PY) run_eval.py --db ../$(DB) --out ../$(RESULTS) --agent claude

report-data:   ## gold tables -> reports/sources/secom/*.csv for the Evidence.dev dashboard
	$(PY) analysis/export_report_data.py --db $(DB) --results $(RESULTS)

test:
	BT2_DB=$(DB) $(PY) -m pytest -q tests

clean:
	rm -rf warehouse data/raw_fixture data/fixture dbt/target dbt/logs
