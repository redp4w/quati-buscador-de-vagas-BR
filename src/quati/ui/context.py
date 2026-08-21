from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from quati.config import (
    AIConfigurationVault,
    JobSourceConfiguration,
    JobSourceConfigurationVault,
    Settings,
)
from quati.plugins import build_plugins
from quati.profile import ProfileVault
from quati.resumes import ResumeVault
from quati.security import DeviceSecretStore, validate_local_passphrase
from quati.storage import SQLiteJobRepository

_VAULT_LABELS = {
    "profile": "Perfil",
    "resumes": "Currículos",
    "ai": "Inteligência artificial",
    "sources": "Fontes públicas",
}


def database_path() -> Path:
    configured = os.environ.get("QUATI_DB") or os.environ.get("JOBHUNTER_DB")
    if configured:
        return Path(configured).resolve()
    current = Path("data/quati.sqlite3")
    legacy = Path("data/jobhunterbr.sqlite3")
    # Mantém instalações existentes acessíveis; instalações novas usam o nome QUATI.
    return (legacy if legacy.exists() and not current.exists() else current).resolve()


@st.cache_resource
def _repository(path: str) -> SQLiteJobRepository:
    return SQLiteJobRepository(path)


def get_plugins() -> dict[str, object]:
    return build_plugins(get_job_source_configuration())


def get_repository() -> SQLiteJobRepository:
    return _repository(str(database_path()))


def profile_vault() -> ProfileVault:
    return ProfileVault(database_path().parent / "candidate-profile.enc")


def resume_vault() -> ResumeVault:
    return ResumeVault(database_path().parent / "candidate-resumes.enc")


def ai_configuration_vault() -> AIConfigurationVault:
    return AIConfigurationVault(database_path().parent / "ai-configuration.enc")


def job_source_configuration_vault() -> JobSourceConfigurationVault:
    return JobSourceConfigurationVault(database_path().parent / "job-source-configuration.enc")


def get_job_source_configuration() -> JobSourceConfiguration:
    local = st.session_state.get("job_source_configuration")
    if isinstance(local, JobSourceConfiguration):
        return local
    settings = Settings()
    return JobSourceConfiguration(
        adzuna_app_id=(
            settings.adzuna_app_id.get_secret_value() if settings.adzuna_app_id else ""
        ),
        adzuna_app_key=(
            settings.adzuna_app_key.get_secret_value() if settings.adzuna_app_key else ""
        ),
    )


def get_ai_settings() -> Settings:
    configuration = st.session_state.get("ai_configuration")
    return configuration.to_settings() if configuration is not None else Settings()


def initialize_session() -> None:
    st.session_state.setdefault("candidate_profile", None)
    st.session_state.setdefault("resume_library", None)
    st.session_state.setdefault("application_bundle", None)
    st.session_state.setdefault("ai_configuration", None)
    st.session_state.setdefault("job_source_configuration", None)
    st.session_state.setdefault("assistant_messages", [])
    st.session_state.setdefault("flash_message", None)
    st.session_state.setdefault("local_session_started", False)
    st.session_state.setdefault("vault_passphrases", {})
    st.session_state.setdefault("local_protection_mode", "")


def vault_passphrase(vault_name: str) -> str:
    if vault_name not in _VAULT_LABELS:
        raise ValueError("Cofre local inválido.")
    passphrase = st.session_state.get("vault_passphrases", {}).get(vault_name)
    if not st.session_state.get("local_session_started") or not passphrase:
        raise ValueError("Inicie a sessão local para acessar dados cifrados.")
    return passphrase


def start_local_session(
    primary_passphrase: str,
) -> None:
    if primary_passphrase:
        validate_local_passphrase(primary_passphrase)
        primary = primary_passphrase
        mode = "Senha da sessão"
    else:
        primary = DeviceSecretStore().get_or_create()
        mode = "Cofre seguro do sistema"

    configured = {name: primary for name in _VAULT_LABELS}

    vaults = {
        "profile": profile_vault(),
        "resumes": resume_vault(),
        "ai": ai_configuration_vault(),
        "sources": job_source_configuration_vault(),
    }
    loaded: dict[str, object] = {
        "profile": None,
        "resumes": [],
        "ai": None,
        "sources": None,
    }
    for name, vault in vaults.items():
        if not vault.exists():
            continue
        try:
            loaded[name] = vault.load(configured[name])
            if not vault.uses_current_format():
                vault.save(loaded[name], primary)
        except ValueError as exc:
            label = _VAULT_LABELS[name]
            raise ValueError(f"Não foi possível abrir {label}: {exc}") from exc

    st.session_state["candidate_profile"] = loaded["profile"]
    st.session_state["resume_library"] = loaded["resumes"]
    st.session_state["ai_configuration"] = loaded["ai"]
    st.session_state["job_source_configuration"] = loaded["sources"]
    st.session_state["application_bundle"] = None
    st.session_state["assistant_messages"] = []
    st.session_state["vault_passphrases"] = configured
    st.session_state["local_protection_mode"] = mode
    st.session_state["local_session_started"] = True


def end_local_session() -> None:
    sensitive_prefixes = (
        "profile_field_",
        "profile_preference_",
        "profile_import_file_",
        "job_search_",
        "ai_api_key_",
        "source_api_",
        "assistant_",
    )
    for key in tuple(st.session_state):
        if key.startswith(sensitive_prefixes):
            st.session_state.pop(key, None)
    st.session_state["candidate_profile"] = None
    st.session_state["resume_library"] = None
    st.session_state["application_bundle"] = None
    st.session_state["ai_configuration"] = None
    st.session_state["job_source_configuration"] = None
    st.session_state["assistant_messages"] = []
    st.session_state["vault_passphrases"] = {}
    st.session_state["local_protection_mode"] = ""
    st.session_state["local_session_started"] = False


def shutdown_request_path() -> Path:
    configured = os.environ.get("QUATI_SHUTDOWN_REQUEST")
    path = Path(configured).resolve() if configured else database_path().parent / "shutdown.request"
    allowed_directories = {database_path().parent, Path("data").resolve()}
    if path.parent not in allowed_directories:
        raise ValueError("O pedido de encerramento não passou na validação de caminho.")
    return path


def request_app_shutdown() -> None:
    """Pede ao iniciador local que encerre toda a árvore de processos do app."""
    path = shutdown_request_path()
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("O arquivo de encerramento não pode ser um link.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("shutdown\n", encoding="ascii")


def reset_local_account(*, secret_store: DeviceSecretStore | None = None) -> None:
    """Apaga somente os arquivos locais conhecidos e fecha o banco antes da remoção."""
    store = secret_store or DeviceSecretStore()
    store.delete()

    database = database_path()
    data_directory = database.parent
    paths = (
        database,
        Path(f"{database}-wal"),
        Path(f"{database}-shm"),
        data_directory / "candidate-profile.enc",
        data_directory / "candidate-resumes.enc",
        data_directory / "ai-configuration.enc",
        data_directory / "job-source-configuration.enc",
    )
    if any(path.parent != data_directory for path in paths):
        raise ValueError("Os arquivos locais não passaram na validação de caminho.")

    try:
        get_repository().close()
    finally:
        _repository.clear()
    for path in paths:
        path.unlink(missing_ok=True)


def reset_private_vaults(*, secret_store: DeviceSecretStore | None = None) -> None:
    """Recomeça os dados privados sem apagar vagas públicas nem histórico."""
    store = secret_store or DeviceSecretStore()
    store.delete()
    data_directory = database_path().parent
    paths = (
        data_directory / "candidate-profile.enc",
        data_directory / "candidate-resumes.enc",
        data_directory / "ai-configuration.enc",
        data_directory / "job-source-configuration.enc",
    )
    if any(path.parent != data_directory or path.is_symlink() for path in paths):
        raise ValueError("Os cofres locais não passaram na validação de caminho.")
    for path in paths:
        path.unlink(missing_ok=True)
    end_local_session()


def render_local_session_gate() -> bool:
    if st.session_state.get("local_session_started"):
        with st.sidebar:
            with st.container(key="session_controls", gap="xsmall"):
                st.caption(st.session_state.get("local_protection_mode", "Sessão local"))
                with st.container(
                    horizontal=True,
                    horizontal_alignment="distribute",
                    gap="xsmall",
                ):
                    if st.button("Bloquear", icon=":material/lock:"):
                        end_local_session()
                        st.rerun()
                    if st.button(
                        "Encerrar",
                        type="primary",
                        icon=":material/power_settings_new:",
                        key="shutdown_app",
                        help="Fecha o servidor local e libera a porta do aplicativo.",
                    ):
                        try:
                            request_app_shutdown()
                            end_local_session()
                            st.info("Encerrando o Q.U.A.T.I.…")
                            st.stop()
                        except (OSError, ValueError) as exc:
                            st.error(f"Não foi possível encerrar: {exc}")
        return True

    existing = {
        "profile": profile_vault().exists(),
        "resumes": resume_vault().exists(),
        "ai": ai_configuration_vault().exists(),
        "sources": job_source_configuration_vault().exists(),
    }
    asset_dir = Path(__file__).parents[1] / "assets"
    st.html(
        """
        <style>
        [data-testid="stMain"] { overflow: hidden; }
        [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: none; }
        .st-key-access_viewport {
            position: fixed;
            inset: 0;
            z-index: 999998;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            padding: .75rem;
            background:
                radial-gradient(circle at 50% 42%, rgba(255, 23, 56, .08), transparent 28rem),
                #060807;
        }
        .st-key-access_viewport [data-testid="stVerticalBlock"] {
            align-items: center;
        }
        .quati-access-copy {
            margin: -.2rem 0 .25rem;
            text-align: center;
            font-family: var(--font-monospace);
            line-height: 1.25;
        }
        .quati-access-copy strong {
            display: block;
            color: rgba(246, 248, 246, .82);
            font-size: .70rem;
            letter-spacing: .11em;
        }
        .quati-access-copy small {
            display: block;
            margin-top: .18rem;
            color: rgba(246, 248, 246, .56);
            font-size: .65rem;
            letter-spacing: .025em;
        }
        .st-key-profile_gate [data-testid="stCaptionContainer"] {
            font-size: .64rem;
            color: rgba(246, 248, 246, .58);
            text-align: center;
        }
        .st-key-profile_gate [data-testid="stImage"] {
            width: 300px !important;
            max-width: 86vw;
        }
        .st-key-profile_gate [data-testid="stImage"] img {
            width: 300px;
            max-width: 86vw;
            height: auto;
        }
        @media (max-height: 760px) {
            .st-key-profile_gate { padding-block: .55rem; }
            .st-key-profile_gate [data-testid="stImage"] img { max-height: 265px; width: auto; }
        }
        </style>
        """
    )
    gate = st.container(
        key="access_viewport",
        horizontal_alignment="center",
        vertical_alignment="center",
        gap=None,
    )
    with gate.container(
        width=470,
        horizontal_alignment="center",
        key="profile_gate",
        gap="xsmall",
    ):
        st.image(str(asset_dir / "quati-inicio-scan.gif"))
        st.html(
            """
            <div class="quati-access-copy">
                <strong>SENHA (OPCIONAL)</strong>
                <small>Deixe vazio para usar o cofre seguro do Windows</small>
            </div>
            """
        )
        if st.session_state.pop("private_vaults_reset", False):
            st.success("Perfil privado redefinido. As vagas e o histórico foram preservados.")
        with st.form("local_session_start", clear_on_submit=True, border=False):
            primary = st.text_input(
                "Senha",
                type="password",
                label_visibility="collapsed",
                placeholder="",
                help="A senha própria fica apenas na memória enquanto o app está aberto.",
            )
            st.caption("Guarde bem a senha, sem ela o perfil não pode ser recuperado")
            submitted = st.form_submit_button(
                "Entrar",
                type="primary",
                icon=":material/lock_open:",
                width="stretch",
            )

        if any(existing.values()):
            with st.expander("Esqueci a senha", icon=":material/key_off:"):
                st.warning(
                    "Não existe senha mestra. A redefinição apaga somente Perfil, currículos e "
                    "configurações cifradas; as vagas públicas e o histórico são mantidos."
                )
                confirmed = st.checkbox(
                    "Entendo que os dados privados cifrados não poderão ser recuperados",
                    key="confirm_private_vault_reset",
                )
                if st.button(
                    "Redefinir perfil privado",
                    icon=":material/restart_alt:",
                    disabled=not confirmed,
                    width="stretch",
                ):
                    try:
                        reset_private_vaults()
                        st.session_state["private_vaults_reset"] = True
                        st.rerun()
                    except (OSError, ValueError) as exc:
                        st.error(f"Não foi possível redefinir: {exc}")

        if st.button(
            "Fechar Q.U.A.T.I.",
            icon=":material/power_settings_new:",
            width="stretch",
            key="shutdown_from_gate",
        ):
            try:
                request_app_shutdown()
                st.info("Encerrando o Q.U.A.T.I.…")
                st.stop()
            except (OSError, ValueError) as exc:
                st.error(f"Não foi possível encerrar: {exc}")

    if submitted:
        try:
            start_local_session(primary)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
            if not primary and any(existing.values()):
                st.info("Se estes dados já existiam, informe a senha usada para protegê-los.")
    return False


def flash(message: str) -> None:
    st.session_state["flash_message"] = message


def render_flash() -> None:
    message = st.session_state.pop("flash_message", None)
    if message:
        st.success(message)
