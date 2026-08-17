import pytest

from us_mediakit.providers import registry
from us_mediakit.providers.claid_ai import ClaidAiProvider
from us_mediakit.providers.real_esrgan import RealEsrganProvider
from us_mediakit.providers.resolution import NoProviderConfiguredError
from us_mediakit.providers.vision_chat import OpenAICompatibleVisionProvider


@pytest.fixture(autouse=True)
def _clear_config_cache():
    registry.load_provider_config.cache_clear()
    yield
    registry.load_provider_config.cache_clear()


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "providers.yaml"
    path.write_text(
        """
providers:
  caption:
    default: "self-hosted"
    base_url: "http://localhost:8803/v1"
    model: "gemma-vision"
  ai_upscale:
    default: "real-esrgan"
    registered:
      real-esrgan:
        endpoint: "http://localhost:8801"
      claid-ai:
        api_key_env: "CLAID_TEST_KEY"
""",
        encoding="utf-8",
    )
    return path


def test_load_provider_config_missing_file_returns_empty():
    assert registry.load_provider_config("/does/not/exist.yaml") == {"providers": {}}


def test_get_instance_default(config_file, monkeypatch):
    monkeypatch.setenv(registry.CONFIG_PATH_ENV_VAR, str(config_file))
    assert registry.get_instance_default("ai_upscale") == "real-esrgan"
    assert registry.get_instance_default("caption") == "self-hosted"


def test_build_ai_upscale_provider_real_esrgan(config_file, monkeypatch):
    monkeypatch.setenv(registry.CONFIG_PATH_ENV_VAR, str(config_file))
    provider = registry.build_ai_upscale_provider("real-esrgan")
    assert isinstance(provider, RealEsrganProvider)


def test_build_ai_upscale_provider_claid_ai_reads_api_key_from_env(config_file, monkeypatch):
    monkeypatch.setenv(registry.CONFIG_PATH_ENV_VAR, str(config_file))
    monkeypatch.setenv("CLAID_TEST_KEY", "secret-123")
    provider = registry.build_ai_upscale_provider("claid-ai")
    assert isinstance(provider, ClaidAiProvider)


def test_build_ai_upscale_provider_unregistered_raises(config_file, monkeypatch):
    monkeypatch.setenv(registry.CONFIG_PATH_ENV_VAR, str(config_file))
    with pytest.raises(NoProviderConfiguredError):
        registry.build_ai_upscale_provider("seedvr2-3b")


def test_build_caption_provider(config_file, monkeypatch):
    monkeypatch.setenv(registry.CONFIG_PATH_ENV_VAR, str(config_file))
    provider = registry.build_caption_provider()
    assert isinstance(provider, OpenAICompatibleVisionProvider)


def test_build_caption_provider_unconfigured_raises(monkeypatch):
    monkeypatch.delenv(registry.CONFIG_PATH_ENV_VAR, raising=False)
    with pytest.raises(NoProviderConfiguredError):
        registry.build_caption_provider()
