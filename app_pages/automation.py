import streamlit as st

from quati.core.browser import PlaywrightBrowser
from quati.core.browser.url_safety import validate_public_https_url
from quati.domain.job import safe_table_text
from quati.services import SearchScheduler
from quati.ui import get_plugins, get_repository
from quati.ui.context import flash, render_flash

repository = get_repository()
plugins = get_plugins()
render_flash()
st.header("Buscas agendadas")
st.caption(
    "Repita a coleta de uma URL pública em intervalos definidos e receba alertas de vagas "
    "novas ou alteradas. Nenhuma candidatura é enviada automaticamente."
)

with st.container(border=True):
    st.subheader("Como funciona")
    st.markdown(
        "1. Escolha uma fonte, cole a URL pública da busca e defina a frequência.  \n"
        "2. O executor local abre apenas os agendamentos que já chegaram ao horário.  \n"
        "3. Vagas novas ou alteradas entram em **Histórico de vagas** e geram alertas.  \n"
        "4. Para parar temporariamente, desative. Para excluir, selecione e use "
        "**Remover agendamento**."
    )
    st.info(
        "O Q.U.A.T.I. aberto não transforma esta página em um serviço de segundo plano. Use "
        "“Executar buscas pendentes agora”, o Agendador de Tarefas do Windows ou o serviço "
        "scheduler do Docker."
    )
    st.caption(
        "Remover um agendamento não apaga as vagas, alertas ou registros de buscas já salvos."
    )

INTERVAL_LABELS = {
    60: "A cada hora",
    360: "A cada 6 horas",
    720: "A cada 12 horas",
    1_440: "Uma vez por dia",
    10_080: "Uma vez por semana",
}

with st.form("create_schedule", border=True):
    source = st.selectbox(
        "Fonte",
        list(plugins),
        format_func=lambda key: plugins[key].display_name,
    )
    entry_url = st.text_input("URL pública")
    interval = st.selectbox(
        "Frequência",
        list(INTERVAL_LABELS),
        index=3,
        format_func=INTERVAL_LABELS.get,
    )
    create = st.form_submit_button("Criar agendamento", icon=":material/schedule:")
if create:
    try:
        plugin = plugins[source]
        safe_url = plugin.prepare_entry_url(entry_url)
        safe_url = validate_public_https_url(safe_url, plugin.allowed_hosts)
        repository.create_schedule(source, safe_url, interval_minutes=int(interval))
        flash("Agendamento criado.")
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))

schedules = repository.list_schedules()
if schedules:
    st.subheader("Agendamentos existentes")
    st.dataframe(
        [
            {
                "ID": item.id,
                "Fonte": (
                    plugins[item.source].display_name if item.source in plugins else item.source
                ),
                "Ativo": item.enabled,
                "Frequência": INTERVAL_LABELS.get(
                    item.interval_minutes, f"{item.interval_minutes} minutos"
                ),
                "Próxima execução": item.next_run_at.strftime("%d/%m/%Y %H:%M UTC"),
                "URL": item.entry_url,
            }
            for item in schedules
        ],
        hide_index=True,
        column_config={"ID": None, "URL": st.column_config.LinkColumn("URL")},
        key="schedules_table",
    )
    schedule_labels = {
        (
            f"#{item.id} — "
            f"{plugins[item.source].display_name if item.source in plugins else item.source}"
        ): item
        for item in schedules
    }
    selected_schedule_label = st.selectbox(
        "Escolha o agendamento que deseja gerenciar",
        list(schedule_labels),
    )
    selected_schedule = schedule_labels[selected_schedule_label]
    with st.container(horizontal=True):
        if st.button(
            "Desativar" if selected_schedule.enabled else "Ativar",
            icon=":material/power_settings_new:",
        ):
            repository.set_schedule_enabled(selected_schedule.id, not selected_schedule.enabled)
            flash("Agendamento atualizado.")
            st.rerun()
        if st.button(
            "Remover agendamento",
            icon=":material/delete:",
            help="Remove somente esta programação; os resultados já coletados permanecem.",
        ):
            repository.delete_schedule(selected_schedule.id)
            flash("Agendamento removido. O histórico e as vagas foram preservados.")
            st.rerun()
    if st.button("Executar buscas pendentes agora", icon=":material/play_arrow:"):
        with st.status("Executando buscas...", expanded=True) as status:
            results = SearchScheduler(repository, PlaywrightBrowser()).run_due(plugins)
            status.update(label="Execução concluída", state="complete", expanded=False)
        flash(f"{len(results)} busca(s) concluída(s).")
        st.rerun()
else:
    st.info(
        "Você ainda não criou uma busca agendada. Preencha o formulário acima para começar."
    )

st.subheader("Alertas")
alerts = repository.list_alerts(limit=100)
if alerts:
    st.dataframe(
        [
            {
                "Lido": item.read,
                "Quando": item.created_at.strftime("%d/%m/%Y %H:%M UTC"),
                "Tipo": "Nova" if item.kind == "new" else "Atualizada",
                "Mensagem": safe_table_text(item.message),
            }
            for item in alerts
        ],
        hide_index=True,
        key="alerts_table",
    )
    if st.button("Marcar todos como lidos", icon=":material/done_all:"):
        repository.mark_all_alerts_read()
        flash("Alertas marcados como lidos.")
        st.rerun()
else:
    st.info("Ainda não há alertas.")
