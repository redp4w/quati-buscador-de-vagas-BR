import streamlit as st

from quati.config import JobSourceConfiguration
from quati.portals import JOB_PORTALS
from quati.ui import (
    get_job_source_configuration,
    job_source_configuration_vault,
    vault_passphrase,
)
from quati.ui.context import flash, render_flash

render_flash()
source_configuration = get_job_source_configuration()

st.header("Adzuna e fontes de vagas")
st.caption(
    "Configure aqui as integrações de coleta. Seus dados pessoais, currículos e preferências "
    "de IA ficam em áreas separadas e não são enviados à Adzuna."
)

with st.container(border=True):
    status = "Ativa" if source_configuration.adzuna_enabled else "Não configurada"
    st.subheader("Adzuna")
    st.badge(
        status,
        icon=":material/check_circle:" if source_configuration.adzuna_enabled else ":material/key:",
        color="green" if source_configuration.adzuna_enabled else "gray",
    )
    st.write(
        "A Adzuna amplia a busca automática pela API oficial. Para ativá-la, crie gratuitamente "
        "um App ID e uma app key; não existe chave pública compartilhada."
    )
    st.caption(
        "As chaves ficam cifradas no cofre local e só são usadas nas requisições à Adzuna."
    )
    st.link_button(
        "Criar credenciais na Adzuna",
        "https://developer.adzuna.com/register",
        icon=":material/open_in_new:",
    )

    with st.form("adzuna_configuration", clear_on_submit=True, border=False):
        adzuna_app_id = st.text_input(
            "App ID",
            type="password",
            autocomplete="off",
            key="source_api_adzuna_app_id",
        )
        adzuna_app_key = st.text_input(
            "App key",
            type="password",
            autocomplete="off",
            key="source_api_adzuna_app_key",
        )
        save_adzuna = st.form_submit_button(
            "Salvar e ativar",
            type="primary",
            icon=":material/save:",
        )

    if save_adzuna:
        try:
            updated_sources = JobSourceConfiguration(adzuna_app_id, adzuna_app_key)
            if not updated_sources.adzuna_enabled:
                raise ValueError("Informe o App ID e a app key da Adzuna.")
            job_source_configuration_vault().save(
                updated_sources,
                vault_passphrase("sources"),
            )
            st.session_state["job_source_configuration"] = updated_sources
            st.session_state.pop("job_search_automatic_sources", None)
            flash("Adzuna ativada para as próximas buscas.")
            st.rerun()
        except (OSError, ValueError) as exc:
            st.error(str(exc))

    if source_configuration.adzuna_enabled and st.button(
        "Desativar e remover chaves",
        icon=":material/key_off:",
    ):
        try:
            disabled_sources = JobSourceConfiguration()
            job_source_configuration_vault().save(
                disabled_sources,
                vault_passphrase("sources"),
            )
            st.session_state["job_source_configuration"] = disabled_sources
            st.session_state.pop("job_search_automatic_sources", None)
            flash("Adzuna desativada e chaves removidas do cofre.")
            st.rerun()
        except (OSError, ValueError) as exc:
            st.error(str(exc))

st.subheader("Catálogo de fontes")
st.caption(
    "Automática importa vagas; Assistida prepara a pesquisa no portal; Por URL coleta uma página "
    "pública específica; No navegador mantém toda a navegação fora do Q.U.A.T.I."
)
mode_labels = {
    "automatic": "Automática",
    "partial": "Por URL",
    "assisted": "Assistida",
    "external": "No navegador",
}
st.dataframe(
    [
        {
            "Fonte": portal.label,
            "Tipo": "ATS por empresa" if portal.kind == "ats" else "Portal",
            "Modo": mode_labels[portal.search_mode],
            "Como funciona": portal.note,
            "Site": portal.access_url,
        }
        for portal in JOB_PORTALS
    ],
    hide_index=True,
    height=460,
    width="stretch",
    column_config={"Site": st.column_config.LinkColumn(display_text="Abrir")},
    key="job_sources_catalog",
)
