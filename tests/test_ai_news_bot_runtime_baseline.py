from pathlib import Path


def test_ai_news_bot_has_shared_python_resolver():
    source = Path("ai_news_bot/scripts/resolve_python.sh").read_text(encoding="utf-8")

    assert "MIN_PYTHON_MINOR=10" in source
    assert "sys.version_info" in source


def test_ai_news_bot_has_project_venv_bootstrap_script():
    source = Path("ai_news_bot/scripts/setup_venv.sh").read_text(encoding="utf-8")

    assert "resolve_python.sh" in source
    assert "-m venv" in source
    assert ".venv/bin/python" in source
    assert "requirements.txt" in source


def test_ai_news_bot_start_scripts_use_shared_resolver():
    cron_source = Path("ai_news_bot/run_bot_cron.sh").read_text(encoding="utf-8")
    local_source = Path("ai_news_bot/run_local.sh").read_text(encoding="utf-8")

    assert "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13" not in cron_source
    assert "python3.13" not in local_source
    assert "ai_news_bot/scripts/resolve_python.sh" in cron_source
    assert "ai_news_bot/scripts/resolve_python.sh" in local_source
    assert "ai_news_bot/scripts/setup_venv.sh" in local_source


def test_ai_news_bot_readme_uses_resolver_based_commands():
    source = Path("ai_news_bot/README_news_bot.md").read_text(encoding="utf-8")

    assert "bash run_local.sh" in source
    assert "python3 run_scheduler.py --now" not in source
    assert "bash scripts/setup_venv.sh" in source
