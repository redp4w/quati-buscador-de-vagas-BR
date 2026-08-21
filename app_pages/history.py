import streamlit as st

from quati.domain.job import safe_table_text
from quati.ui import get_repository

repository = get_repository()
st.header("Histórico de vagas e buscas")
st.caption(
    "Aqui ficam as coletas realizadas e as alterações detectadas nos anúncios. "
    "Falhas técnicas e mensagens do aplicativo ficam em Logs técnicos."
)

st.subheader("Buscas realizadas")
runs = repository.list_runs(limit=100)
if runs:
    st.dataframe(
        [
            {
                "Início": run.started_at.strftime("%d/%m/%Y %H:%M UTC"),
                "Fonte": safe_table_text(run.source),
                "Status": safe_table_text(run.status),
                "Encontradas": run.found_count,
                "Novas": run.inserted_count,
                "Atualizadas": run.updated_count,
                "Erro": safe_table_text(run.error_message),
            }
            for run in runs
        ],
        hide_index=True,
        key="collection_history",
    )
else:
    st.info("Ainda não há buscas no histórico.")

st.subheader("Mudanças nas vagas")
changes = repository.list_changes(limit=100)
if changes:
    rows = []
    for change in changes:
        try:
            job = repository.get_job(change.job_id)
            label = f"{job.title} — {job.company}"
        except ValueError:
            label = f"Vaga #{change.job_id}"
        rows.append(
            {
                "Quando": change.changed_at.strftime("%d/%m/%Y %H:%M UTC"),
                "Vaga": safe_table_text(label),
                "Campos": ", ".join(change.changed_fields),
            }
        )
    st.dataframe(rows, hide_index=True, key="change_history")
else:
    st.info("Nenhuma vaga mudou desde a última coleta.")
