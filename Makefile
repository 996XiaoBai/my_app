.PHONY: news ui schedule help

PYTHON_BIN := $(shell bash test_platform/scripts/resolve_python.sh $(CURDIR) 2>/dev/null || command -v python3)

help:
	@echo "Available commands:"
	@echo "  make news      - Run AI News Bot immediately"
	@echo "  make ui        - Start Review Agent Streamlit UI"
	@echo "  make schedule  - Start AI News Bot Scheduler"

news:
	$(PYTHON_BIN) cli.py news

ui:
	$(PYTHON_BIN) cli.py ui

schedule:
	$(PYTHON_BIN) cli.py scheduler
