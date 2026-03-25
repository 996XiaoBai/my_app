import importlib
import sys

import dotenv


def reload_test_platform_config(monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    sys.modules.pop("test_platform.config", None)
    import test_platform.config as config_module

    return importlib.reload(config_module)


def test_agent_config_prefers_test_platform_specific_dify_settings(monkeypatch):
    monkeypatch.setenv("TEST_PLATFORM_DIFY_API_KEY", "platform-key")
    monkeypatch.setenv("TEST_PLATFORM_DIFY_USER_ID", "platform-user")
    monkeypatch.setenv("DIFY_API_KEY", "shared-key")
    monkeypatch.setenv("DIFY_USER_ID", "shared-user")

    config_module = reload_test_platform_config(monkeypatch)

    assert config_module.AgentConfig.DIFY_API_KEY == "platform-key"
    assert config_module.AgentConfig.DIFY_USER_ID == "platform-user"


def test_agent_config_falls_back_to_shared_dify_settings(monkeypatch):
    monkeypatch.delenv("TEST_PLATFORM_DIFY_API_KEY", raising=False)
    monkeypatch.delenv("TEST_PLATFORM_DIFY_USER_ID", raising=False)
    monkeypatch.setenv("DIFY_API_KEY", "shared-key")
    monkeypatch.setenv("DIFY_USER_ID", "shared-user")

    config_module = reload_test_platform_config(monkeypatch)

    assert config_module.AgentConfig.DIFY_API_KEY == "shared-key"
    assert config_module.AgentConfig.DIFY_USER_ID == "shared-user"
