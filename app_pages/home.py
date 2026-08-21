import streamlit as st

from quati.domain.job import safe_table_text
from quati.ui import get_ai_settings, get_repository
from quati.ui.context import render_flash


def assistant_label() -> str:
    provider = get_ai_settings().ai_provider
    return {
        "none": "Local",
        "ollama": "Ollama",
        "gemini": "Gemini",
        "openai_compatible": "API modular",
    }.get(provider, "Configurável")


repository = get_repository()
render_flash()

stats = repository.stats()
resumes = st.session_state.get("resume_library") or []
main_column, alerts_column = st.columns([1.25, 1], gap="large")

with main_column:
    st.subheader("Seu ponto de partida")
    with st.container(horizontal=True):
        st.metric("Currículos", len(resumes), border=True)
        st.metric("Assistente", assistant_label(), border=True)
        st.metric("Vagas únicas", stats["total_jobs"], border=True)

    with st.container(border=True):
        st.subheader("Primeiros passos")
        st.markdown(
            "1. Complete seus **Dados pessoais** ou pesquise sem cadastro.  \n"
            "2. Escolha os portais e busque vagas públicas.  \n"
            "3. Selecione oportunidades e prepare o currículo.  \n"
            "4. Abra o anúncio original e conclua a candidatura."
        )

    st.caption("Atalhos")
    with st.container(horizontal=True):
        st.page_link("app_pages/profile.py", label="Dados pessoais", icon=":material/person:")
        st.page_link("app_pages/jobs.py", label="Buscar vagas", icon=":material/search:")
        st.page_link(
            "app_pages/applications.py",
            label="Preparar currículo",
            icon=":material/edit_document:",
        )

with alerts_column:
    alerts = repository.list_alerts(unread_only=True, limit=10)
    st.subheader("Alertas recentes")
    with st.container(border=True):
        if alerts:
            st.dataframe(
                [
                    {
                        "Quando": alert.created_at.strftime("%d/%m %H:%M"),
                        "Tipo": "Nova" if alert.kind == "new" else "Atualizada",
                        "Mensagem": safe_table_text(alert.message),
                    }
                    for alert in alerts
                ],
                hide_index=True,
                key="home_alerts",
                height=390,
                width="stretch",
            )
        else:
            st.info("Nenhum alerta novo por enquanto.")

st.caption(
    "O Q.U.A.T.I. pesquisa fontes públicas, mantém seus dados neste computador e deixa o envio "
    "da candidatura sob seu controle."
)
