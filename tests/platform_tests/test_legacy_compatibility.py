from pathlib import Path


def test_legacy_tapd_client_reexports_infrastructure_client():
    from test_platform.infrastructure.tapd_client import TAPDClient as InfrastructureTAPDClient
    from test_platform.services.tapd_client import TAPDClient as LegacyTAPDClient

    assert LegacyTAPDClient is InfrastructureTAPDClient


def test_legacy_agent_config_reexports_main_agent_config():
    from test_platform.config import AgentConfig as MainAgentConfig
    from test_platform.services.agent_config import AgentConfig as LegacyAgentConfig

    assert LegacyAgentConfig is MainAgentConfig


def test_legacy_streamlit_entry_is_a_lightweight_wrapper():
    source = Path("test_platform/ui/streamlit_app.py").read_text(encoding="utf-8")

    assert 'runpy.run_module("test_platform.app", run_name="__main__")' in source
    assert "from test_platform.core.services.review_service import ReviewService" not in source
