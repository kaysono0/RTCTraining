.PHONY: cert run-webrtc run-dashboard test test-unit test-e2e urls harness-smoke automation-run-once automation-run-continuous automation-task-help

PYTHON ?= .venv/bin/python

cert:
	$(PYTHON) scripts/generate_cert.py

run-webrtc:
	$(PYTHON) -m src.webrtc.chat_server run

run-dashboard:
	$(PYTHON) -m src.dashboard.server run

test:
	$(PYTHON) -m pytest tests -v

test-unit:
	$(PYTHON) -m pytest tests -v --ignore=tests/test_playwright_e2e.py

test-e2e:
	$(PYTHON) -m pytest tests/test_playwright_e2e.py -v

urls:
	$(PYTHON) scripts/print_lan_urls.py

harness-smoke:
	$(PYTHON) -m automation.harness.smoke --python $(PYTHON) --generate-cert

automation-run-once:
	$(PYTHON) -m automation.runner.orchestrator run-once

automation-run-continuous:
	$(PYTHON) -m automation.runner.orchestrator run-continuous --max-tasks 1

automation-task-help:
	$(PYTHON) -m automation.runner.task_cli --help
