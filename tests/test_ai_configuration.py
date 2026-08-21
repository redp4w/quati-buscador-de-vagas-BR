import pytest

from quati.config import AIConfiguration, AIConfigurationVault


def test_ai_configuration_is_encrypted_and_restored(tmp_path) -> None:
    path = tmp_path / "ai.enc"
    vault = AIConfigurationVault(path)
    configuration = AIConfiguration(
        "gemini",
        "gemini-3.5-flash",
        api_key="secret-gemini-key",  # pragma: allowlist secret
        include_profile_context=True,
        external_consent=True,
    )

    vault.save(configuration, "senha-local-segura")
    restored = vault.load("senha-local-segura")

    assert restored == configuration
    assert b"secret-gemini-key" not in path.read_bytes()
    with pytest.raises(ValueError):
        vault.load("senha-incorreta")


def test_ai_configuration_migrates_preferences_from_version_one(tmp_path) -> None:
    vault = AIConfigurationVault(tmp_path / "legacy-ai.enc")
    vault._vault.save(
        {
            "version": 1,
            "provider": "none",
            "model": "",
            "endpoint": "",
            "api_key": "",
        },
        "senha-local-segura",
    )

    restored = vault.load("senha-local-segura")

    assert not restored.include_profile_context
    assert not restored.external_consent


def test_openai_compatible_endpoint_rejects_private_or_insecure_remote_hosts() -> None:
    with pytest.raises(ValueError):
        AIConfiguration("openai_compatible", "model", "http://example.com/v1")
    with pytest.raises(ValueError):
        AIConfiguration("openai_compatible", "model", "https://127.0.0.2/v1")

    local = AIConfiguration("openai_compatible", "model", "http://127.0.0.1:1234/v1")
    assert not local.to_settings().ai_is_external
