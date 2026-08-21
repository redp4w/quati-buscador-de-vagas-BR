import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import streamlit as st

from quati.ai import (
    detect_seniority,
    detect_work_mode,
    profile_search_requirements,
    rank_jobs_for_profile,
)
from quati.config import load_source_catalog
from quati.core.browser import PlaywrightBrowser
from quati.domain.job import normalized_key, safe_table_text, utc_now
from quati.location import (
    BRAZILIAN_STATES,
    brazilian_cities,
    canonical_brazilian_location,
    split_brazilian_location,
)
from quati.portals import (
    AUTOMATIC_PORTAL_IDS,
    PORTALS_BY_ID,
    SEARCHABLE_PORTAL_IDS,
)
from quati.profile import JOB_LEVELS, WORK_MODES, preference_values
from quati.services import (
    JobCollector,
    MultiSourceDiscovery,
    SearchRequest,
    job_is_pcd_eligible,
    job_matches_search,
)
from quati.ui import (
    get_job_source_configuration,
    get_plugins,
    get_repository,
)
from quati.ui.context import flash, render_flash

repository = get_repository()
plugins = get_plugins()
profile = st.session_state.get("candidate_profile")
source_configuration = get_job_source_configuration()
repository.archive_stale_jobs(older_than_days=60)
render_flash()
st.header("Buscar vagas")
st.caption(
    "Busque vagas públicas nos portais escolhidos. Com um perfil preenchido, os resultados "
    "também recebem uma nota de compatibilidade."
)

if st.session_state.pop("open_prepared_application", False):
    st.switch_page("app_pages/applications.py")

page_layout = st.container(horizontal=True, gap="large")
filters_panel = page_layout.container(width=400)
results_panel = page_layout.container(width="stretch")

SOURCE_LABELS = {portal_id: PORTALS_BY_ID[portal_id].label for portal_id in SEARCHABLE_PORTAL_IDS}
STATE_LABELS = dict(BRAZILIAN_STATES)
RECENCY_LABELS = {
    "24h": "Últimas 24 horas",
    "7d": "Últimos 7 dias",
    "30d": "Últimos 30 dias",
    "any": "Qualquer data",
}
SEARCH_FORM_VERSION = 7
FREE_SEARCH = "Busca livre"
PROFILE_SEARCH = "Compatíveis com o Perfil"
PROFILE_COMPATIBILITY_FLOOR = 70
LOADING_GIF = Path(__file__).parents[1] / "src" / "quati" / "assets" / "quati-loading.gif"


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source.replace("_", " ").title())


def score_label(value: int | None, missing: str) -> str:
    return f"{value}%" if value is not None else missing


def clear_search_city() -> None:
    """Limpa a cidade quando a pessoa escolhe outro estado."""
    st.session_state["job_search_city"] = ""


@contextmanager
def loading_status(label: str):
    """Centraliza o asset animado em uma camada temporária durante a coleta."""
    placeholder = st.empty()
    with placeholder.container(
        key="job_loading_overlay",
        horizontal_alignment="center",
        vertical_alignment="center",
    ):
        with st.container(
            key="job_loading_content",
            width=380,
            horizontal_alignment="center",
            gap="xsmall",
        ):
            if LOADING_GIF.is_file():
                st.image(str(LOADING_GIF))
            st.caption(label, text_alignment="center")
    try:
        yield
    finally:
        placeholder.empty()


def discarded_jobs_label(count: int) -> str:
    noun = "vaga descartada" if count == 1 else "vagas descartadas"
    return f"{count} {noun} por não atender {'ao filtro' if count == 1 else 'aos filtros'}"


profile_roles = list(preference_values(profile.target_roles)) if profile else []
profile_sources = list(SEARCHABLE_PORTAL_IDS)
configured_company_sources = {
    company.source for company in load_source_catalog().companies if company.enabled
}
profile_city, profile_state = split_brazilian_location(
    profile.preferred_location if profile else ""
)
available_automatic_sources = [
    source
    for source in profile_sources
    if source in AUTOMATIC_PORTAL_IDS
    and (source != "adzuna" or source_configuration.adzuna_enabled)
    and source
    in {
        "adzuna",
        "solides",
        "empregos",
        "empregando_brasil",
        "gupy",
        "linkedin",
        "indeed",
        "vagas_com",
        "mindsight",
        "latojobs",
        *configured_company_sources,
    }
]
profile_automatic_sources = list(available_automatic_sources)
profile_assisted_sources = [
    source for source in profile_sources if source not in AUTOMATIC_PORTAL_IDS
]
st.session_state.setdefault("job_search_roles", profile_roles)
st.session_state.setdefault("job_search_levels", [])
st.session_state.setdefault("job_search_modes", [])
st.session_state.setdefault("job_search_pcd_only", False)
st.session_state.setdefault("job_search_automatic_sources", profile_automatic_sources)
st.session_state.setdefault("job_search_assisted_sources", profile_assisted_sources)
st.session_state.setdefault("job_search_state", profile_state)
st.session_state.setdefault("job_search_city", profile_city)
legacy_keywords = profile.skills[:300] if profile else ""
if st.session_state.get("job_search_form_version", 1) < SEARCH_FORM_VERSION:
    if st.session_state.get("job_search_keywords", "") == legacy_keywords:
        st.session_state["job_search_keywords"] = ""
    st.session_state["job_search_form_version"] = SEARCH_FORM_VERSION
    st.session_state.pop("job_search_sources", None)
    st.session_state.pop("job_search_location", None)
    st.session_state.pop("job_search_automatic_sources", None)
    st.session_state.pop("job_search_assisted_sources", None)
    st.session_state["job_search_automatic_sources"] = profile_automatic_sources
    st.session_state["job_search_assisted_sources"] = profile_assisted_sources
st.session_state.setdefault("job_search_keywords", "")
st.session_state.setdefault("job_search_mode", FREE_SEARCH)

with filters_panel.expander("Entenda os modos", icon=":material/info:"):
    st.write(
        "**Automática:** as vagas entram nos resultados.  \n"
        "**Assistida:** a pesquisa abre pronta no portal.  \n"
        "**Por URL:** uma página pública específica é importada quando a fonte permite."
    )

with filters_panel.container(border=True):
    st.caption(
        "Adzuna e catálogo de portais ficam no menu Configurações → Adzuna e fontes."
    )

with filters_panel.container(border=True):
    st.subheader("Buscar vagas públicas")
    search_mode = st.segmented_control(
        "Modo de busca",
        (FREE_SEARCH, PROFILE_SEARCH),
        key="job_search_mode",
        width="stretch",
    )
    profile_mode = search_mode == PROFILE_SEARCH
    profile_issues = profile_search_requirements(profile) if profile_mode else ()

    if profile_mode:
        roles = list(preference_values(profile.target_roles)) if profile else []
        levels = list(preference_values(profile.target_levels)) if profile else []
        modes = list(preference_values(profile.work_modes)) if profile else []
        keywords = ""
        location = profile.preferred_location if profile else ""
        search_radius = int(profile.max_distance_km) if profile else 80
        pcd_only = False
        location_is_valid = not profile_issues
        if profile_issues:
            st.error("Complete no Perfil: " + ", ".join(profile_issues) + ".")
            st.page_link(
                "app_pages/profile.py",
                label="Completar Perfil",
                icon=":material/person_edit:",
            )
        else:
            st.success("Perfil pronto para a busca com compatibilidade mínima de 70%.")
            st.write("**Cargos:** " + " · ".join(roles))
            st.caption(
                f"Níveis: {', '.join(levels)} · Modalidades: {', '.join(modes)} · "
                f"Local: {location or 'Brasil remoto'} · Raio: {search_radius} km"
            )
            st.caption(
                "Cada cargo gera uma consulta separada. Depois da coleta, o cálculo local mantém "
                "somente vagas com 70% ou mais. O Perfil não é enviado aos portais."
            )
    else:
        role_options = list(st.session_state["job_search_roles"])
        roles = st.multiselect(
            "Cargos ou áreas",
            role_options,
            accept_new_options=True,
            max_selections=5,
            key="job_search_roles",
            placeholder="",
            help=("Cada cargo gera uma consulta separada nos portais selecionados."),
        )
        keywords = st.text_input(
            "Palavras adicionais (opcional)",
            key="job_search_keywords",
            help=(
                "A frase é enviada inteira ao portal. Na filtragem local, palavras relevantes "
                "também podem coincidir individualmente; fragmentos de palavras não contam."
            ),
        )
        location_columns = st.columns([1, 2])
        selected_state = location_columns[0].selectbox(
            "Estado",
            ("", *STATE_LABELS),
            format_func=lambda value: f"{value} — {STATE_LABELS[value]}" if value else "",
            key="job_search_state",
            on_change=clear_search_city,
            placeholder="",
        )
        city_options = brazilian_cities(selected_state) if selected_state else ()
        selected_city = location_columns[1].selectbox(
            "Cidade",
            ("", *city_options),
            key="job_search_city",
            disabled=not selected_state,
            placeholder="",
        )
        levels = st.pills(
            "Níveis",
            JOB_LEVELS,
            selection_mode="multi",
            key="job_search_levels",
        )
        modes = st.pills(
            "Modalidades",
            WORK_MODES,
            selection_mode="multi",
            key="job_search_modes",
        )
        pcd_only = st.checkbox(
            "Somente vagas explicitamente indicadas para PCD",
            key="job_search_pcd_only",
            help="Mostra vagas que mencionam PCD ou pessoa com deficiência no anúncio.",
        )
        search_radius = int(profile.max_distance_km) if profile else 80
        try:
            location = canonical_brazilian_location(selected_city, selected_state)
            location_is_valid = True
        except ValueError as exc:
            location = ""
            location_is_valid = False
            st.error(str(exc))
        if selected_city:
            st.caption(
                f"Vagas presenciais e híbridas: até {search_radius} km de {location}. "
                "Para incluir vagas remotas de todo o Brasil, selecione Remoto."
            )
        elif selected_state:
            st.caption(
                "Sem cidade, entram vagas presenciais e híbridas identificadas em "
                f"{selected_state}."
            )
        elif set(modes) == {"Remoto"}:
            st.caption("Sem localização, a busca aceita vagas remotas de todo o Brasil.")
        else:
            st.caption("Sem localização, a busca considera o Brasil inteiro.")

    recency = st.selectbox(
        "Período",
        list(RECENCY_LABELS),
        format_func=RECENCY_LABELS.get,
        index=1,
    )
    with st.expander("Portais de coleta", icon=":material/travel_explore:"):
        automatic_sources = st.multiselect(
            "Coleta automática",
            available_automatic_sources,
            format_func=SOURCE_LABELS.get,
            key="job_search_automatic_sources",
            placeholder="",
            help="As vagas públicas compatíveis entram nos resultados e ficam salvas localmente.",
        )
        assisted_sources = st.multiselect(
            "Busca assistida ou por link",
            [source for source in profile_sources if source not in AUTOMATIC_PORTAL_IDS],
            format_func=SOURCE_LABELS.get,
            key="job_search_assisted_sources",
            placeholder="",
            help="Os filtros são preparados e a pesquisa continua no portal original.",
        )
        st.caption(
            "Greenhouse, Lever, SmartRecruiters, Ashby, Recruitee, Workable e InHire "
            "consultam somente as empresas declaradas no catálogo público."
        )
    sources = (*automatic_sources, *assisted_sources)
    search = st.button(
        "Buscar vagas compatíveis" if profile_mode else "Buscar vagas",
        type="primary",
        icon=":material/search:",
        disabled=not location_is_valid or not sources,
        width="stretch",
    )

if search:
    try:
        request = SearchRequest(
            keywords,
            location,
            sources=tuple(sources),
            recency=recency,
            remote_only=set(modes) == {"Remoto"},
            roles=tuple(roles),
            levels=tuple(levels),
            work_modes=tuple(modes),
            max_distance_km=search_radius,
            pcd_only=pcd_only,
        )
        with loading_status("Preparando e consultando as buscas..."):
            result = MultiSourceDiscovery(repository, PlaywrightBrowser()).collect(request, plugins)
        grouped = defaultdict(lambda: {"found": 0, "failed": 0})
        for item in result.sources:
            if item.collection:
                grouped[item.source]["found"] += item.collection.found
            else:
                grouped[item.source]["failed"] += 1
        details = []
        external_links = []
        for source in request.sources:
            if source not in AUTOMATIC_PORTAL_IDS:
                external_links.append(source_label(source))
                continue
            summary = grouped[source]
            if summary["found"] > 0:
                detail = f"{source_label(source)}: {summary['found']}"
                if summary["failed"]:
                    detail += f" ({summary['failed']} falha(s))"
                details.append(detail)
        st.session_state["job_results_filter"] = (
            ""
            if profile_mode
            else (roles[0] if len(roles) == 1 else (keywords if not roles else ""))
        )
        st.session_state["active_job_search_request"] = request
        st.session_state["active_job_search_mode"] = "profile" if profile_mode else "free"
        st.session_state["profile_compatibility_threshold"] = (
            PROFILE_COMPATIBILITY_FLOOR if profile_mode else 0
        )
        st.session_state["job_results_min_score"] = (
            PROFILE_COMPATIBILITY_FLOOR if profile_mode else 0
        )
        st.session_state["assisted_search_targets"] = result.assisted

        message_parts = []
        if result.inserted > 0:
            message_parts.append(f"{result.inserted} novas encontradas")
        if result.filtered > 0:
            message_parts.append(discarded_jobs_label(result.filtered))

        if details:
            message_parts.append("Fontes: " + ", ".join(details))

        if external_links:
            message_parts.append(f"Links externos: {', '.join(external_links)}")

        if not message_parts:
            message_parts.append("Nenhuma vaga encontrada")

        flash(" · ".join(message_parts))
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))
    except sqlite3.Error:
        st.error("Não foi possível atualizar o banco local. Tente novamente.")

assisted_targets = st.session_state.get("assisted_search_targets") or ()
if assisted_targets:
    with results_panel.container(border=True):
        st.subheader("Continuar nos portais")
        st.write(
            "Os filtros estão prontos. Abra cada pesquisa pública no navegador. Nenhum dado "
            "da página retorna ao Q.U.A.T.I."
        )
        columns = st.columns(2)
        for index, target in enumerate(assisted_targets):
            label = target.label or "vagas"
            columns[index % 2].link_button(
                f"{source_label(target.source)} · {label}",
                target.url,
                icon=":material/open_in_new:",
                width="stretch",
            )
        st.caption(
            "Nessas fontes, o Q.U.A.T.I. não lê nem copia a página de resultados. A candidatura "
            "continua no portal original."
        )

with filters_panel.expander("Coletar uma URL específica", icon=":material/link:"):
    with st.form("collect_jobs", border=False):
        source = st.selectbox(
            "Fonte",
            list(plugins),
            format_func=lambda key: (
                f"{plugins[key].display_name}"
                f"{' — experimental' if plugins[key].experimental else ''}"
            ),
        )
        entry_url = st.text_input("URL pública da busca ou página de vagas")
        collect = st.form_submit_button("Coletar URL", icon=":material/link:")

    if collect:
        try:
            with loading_status("Coletando página pública..."):
                result = JobCollector(repository, PlaywrightBrowser()).collect(
                    plugins[source], entry_url
                )
            flash(
                f"{result.inserted} novas; {result.updated} atualizadas; {result.found} total."
            )
            st.session_state.pop("active_job_search_request", None)
            st.session_state.pop("active_job_search_mode", None)
            st.session_state.pop("profile_compatibility_threshold", None)
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))

stats = repository.stats()
results_panel.caption(
    f"{stats['active_jobs']} ativas · {stats['total_jobs']} no histórico · "
    f"{stats['unread_alerts']} alertas. O app arquiva vagas que não reaparecem por 60 dias."
)

all_jobs = repository.list_jobs(limit=500)
active_search_request = st.session_state.get("active_job_search_request")
if isinstance(active_search_request, SearchRequest):
    all_jobs = [job for job in all_jobs if job_matches_search(job, active_search_request)]
ranked_by_id = {}
if profile is not None:
    ranked = rank_jobs_for_profile(all_jobs, profile)
    ranked_by_id = {item.job.id: item.compatibility for item in ranked}
    all_jobs = [item.job for item in ranked]

compatibility_threshold = 0
if isinstance(active_search_request, SearchRequest) and profile is not None:
    compatibility_threshold = int(
        st.session_state.get("profile_compatibility_threshold", 0)
    )
    if compatibility_threshold:
        all_jobs = [
            job
            for job in all_jobs
            if ranked_by_id[job.id].compatibility_score >= compatibility_threshold
        ]

available_sources = sorted({job.source for job in all_jobs})
results_panel.subheader("Resultados")
if isinstance(active_search_request, SearchRequest):
    scope = active_search_request.location or "Brasil inteiro"
    match_note = (
        f" · compatibilidade mínima {compatibility_threshold}%"
        if compatibility_threshold
        else ""
    )
    results_panel.caption(f"Resultados da última busca: {scope}{match_note}.")
    if results_panel.button(
        "Mostrar todas as vagas armazenadas",
        icon=":material/database:",
        key="clear_active_job_search",
    ):
        st.session_state.pop("active_job_search_request", None)
        st.session_state.pop("active_job_search_mode", None)
        st.session_state.pop("profile_compatibility_threshold", None)
        st.session_state["job_results_min_score"] = 0
        st.rerun()
filter_bar = results_panel.columns([3, 2])
text_query = filter_bar[0].text_input(
    "Filtrar resultados",
    key="job_results_filter",
)
if text_query:
    results_panel.caption(
        "A última busca preencheu este filtro. Limpe o campo para ver todas as vagas."
    )
sort_mode = filter_bar[1].segmented_control(
    "Ordenar por",
    ["Compatibilidade", "Mais recentes"],
    default="Compatibilidade" if profile is not None else "Mais recentes",
)
st.session_state.setdefault("job_results_min_score", compatibility_threshold)
with results_panel.expander("Mais filtros"):
    filter_columns = st.columns(3)
    company_query = filter_columns[0].text_input("Empresa")
    location_query = filter_columns[1].text_input("Cidade ou local")
    display_period = filter_columns[2].selectbox(
        "Vistas no período",
        ("30d", "90d", "all"),
        format_func={
            "30d": "Últimos 30 dias",
            "90d": "Últimos 90 dias",
            "all": "Todo histórico",
        }.get,
    )
    selected_sources = st.multiselect(
        "Fontes",
        available_sources,
        default=available_sources,
        format_func=source_label,
        placeholder="",
    )
    selected_levels = st.pills(
        "Níveis da vaga",
        (*JOB_LEVELS, "Não informado"),
        selection_mode="multi",
    )
    selected_modes = st.pills(
        "Modalidades da vaga",
        (*WORK_MODES, "Não informado"),
        selection_mode="multi",
    )
    only_pcd = st.checkbox("Somente vagas PCD")
    min_score = st.slider(
        "Compatibilidade mínima",
        0,
        100,
        disabled=profile is None,
        key="job_results_min_score",
    )
    only_active = st.checkbox("Somente vagas ativas", value=True)

normalized_text = normalized_key(text_query)
normalized_company = normalized_key(company_query)
normalized_location = normalized_key(location_query)
source_filter = set(selected_sources) & set(available_sources)
level_filter = set(selected_levels)
mode_filter = set(selected_modes)
jobs = []
period_days = {"30d": 30, "90d": 90}.get(display_period)
period_cutoff = utc_now() - timedelta(days=period_days) if period_days else None
for job in all_jobs:
    searchable = normalized_key(f"{job.title} {job.company} {job.location} {job.description}")
    if normalized_text and normalized_text not in searchable:
        continue
    if normalized_company and normalized_company not in normalized_key(job.company):
        continue
    if normalized_location and normalized_location not in normalized_key(job.location):
        continue
    if source_filter and job.source not in source_filter:
        continue
    if only_active and job.status != "active":
        continue
    if period_cutoff and job.last_seen_at < period_cutoff:
        continue
    if level_filter and detect_seniority(job) not in level_filter:
        continue
    if mode_filter and detect_work_mode(job) not in mode_filter:
        continue
    if only_pcd and not job_is_pcd_eligible(job):
        continue
    if profile is not None and ranked_by_id[job.id].compatibility_score < min_score:
        continue
    jobs.append(job)

if sort_mode == "Mais recentes":
    jobs.sort(key=lambda item: item.last_seen_at, reverse=True)
elif profile is not None:
    jobs.sort(
        key=lambda item: (ranked_by_id[item.id].compatibility_score, item.last_seen_at),
        reverse=True,
    )

if profile is None:
    results_panel.info(
        "Preencha o perfil para calcular a compatibilidade. A pesquisa continua disponível."
    )
else:
    with results_panel.expander("Como a compatibilidade é calculada"):
        st.write(
            "O cálculo usa somente o Perfil salvo: cargo 35%, nível 25%, competências 25% "
            "e localização/modalidade 15%. Os filtros da busca não alteram a nota. Uma vaga "
            "um nível acima fica limitada a 70%; dois ou mais níveis acima, a 45%."
        )
        st.caption(
            "Quando falta informação, o cálculo mostra incerteza em vez de presumir uma boa "
            "compatibilidade. A distância usa uma base geográfica offline."
        )
        if not profile.target_roles:
            st.warning("Cadastre cargos de interesse no Perfil para avaliar aderência de cargo.")
        if not profile.target_levels:
            st.warning("Cadastre os níveis aceitos no Perfil para avaliar a senioridade.")

rows = []
for job in jobs:
    compatibility = ranked_by_id.get(job.id)
    rows.append(
        {
            "Anúncio": job.url,
            "Currículo": "✎",
            "Vaga": safe_table_text(
                f"{job.title} · PCD" if job_is_pcd_eligible(job) else job.title
            ),
            "Compatibilidade": compatibility.compatibility_score if compatibility else None,
            "Empresa": safe_table_text(job.company),
            "Local": safe_table_text(job.location),
        }
    )


def prepare_job_from_table() -> None:
    click = st.session_state.get("prepare_job_click")
    if not click:
        return
    row = int(click["row"])
    if not 0 <= row < len(jobs):
        return
    resumes = st.session_state.get("resume_library") or []
    resume_id = "profile" if profile is not None or not resumes else resumes[0].id
    repository.save_application(
        jobs[row].id,
        resume_id=resume_id,
        strategy="tailored",
        status="prepared",
    )
    st.session_state["application_bundle"] = None
    st.session_state["open_prepared_application"] = True
    flash("Vaga enviada para Preparar candidatura.")


event = results_panel.dataframe(
    rows,
    hide_index=True,
    key="jobs_selection",
    on_select="rerun",
    selection_mode="multi-row",
    height=500,
    width="stretch",
    row_height=42,
    column_config={
        "Anúncio": st.column_config.LinkColumn(
            "ABRIR",
            display_text="↗",
            help="Abrir o anúncio original no portal",
            width=72,
            pinned=True,
            alignment="center",
        ),
        "Currículo": st.column_config.ButtonColumn(
            "CV",
            type="tertiary",
            help="Preparar e personalizar o currículo para esta vaga",
            width=82,
            pinned=True,
            alignment="center",
            on_click=prepare_job_from_table,
            key="prepare_job_click",
        ),
        "Compatibilidade": st.column_config.ProgressColumn(
            "Compatibilidade", min_value=0, max_value=100, format="%d%%", width="small"
        ),
        "Vaga": st.column_config.TextColumn("Vaga", pinned=True, width="large"),
        "Empresa": st.column_config.TextColumn("Empresa", width="medium"),
        "Local": st.column_config.TextColumn("Local", width="medium"),
    },
)
selected_indices = event.selection.rows
selected_jobs = [jobs[index] for index in selected_indices if index < len(jobs)]
results_panel.caption(f"{len(jobs)} vaga(s); {len(selected_jobs)} selecionada(s).")

if selected_jobs:
    if profile is not None:
        with results_panel.expander("Detalhes da compatibilidade"):
            for job in selected_jobs:
                compatibility = ranked_by_id[job.id]
                distance = (
                    f"{compatibility.distance_km:.0f} km"
                    if compatibility.distance_km is not None
                    else "não identificada"
                )
                st.text(f"{job.title} — {compatibility.compatibility_score}%")
                st.write(
                    f"Cargo: {score_label(compatibility.role_score, 'não configurado')} · "
                    f"Local: {score_label(compatibility.location_score, 'não configurado')} · "
                    f"Nível: {score_label(compatibility.seniority_score, 'não configurado')} · "
                    f"Competências: {score_label(compatibility.skills_score, 'não avaliado')}"
                )
                st.caption(
                    f"{compatibility.seniority}; {compatibility.work_mode}; distância {distance}. "
                    + "; ".join(compatibility.reasons)
                )
    profile_available = profile is not None
    resumes = st.session_state.get("resume_library") or []
    resume_options = (["profile"] if profile_available else []) + [item.id for item in resumes]
    resume_labels = {"profile": "Gerar usando o Perfil"}
    resume_labels.update({item.id: item.label for item in resumes})
    with results_panel.form("prepare_applications", border=True):
        st.subheader("Preparar candidatura para as vagas selecionadas")
        if resume_options:
            resume_id = st.selectbox(
                "Currículo base", resume_options, format_func=lambda key: resume_labels[key]
            )
            strategy_label = st.segmented_control(
                "Currículo para cada vaga", ["Padrão", "Direcionada"], default="Direcionada"
            )
            prepare = st.form_submit_button(
                "Preparar para aplicar", type="primary", icon=":material/send:"
            )
        else:
            st.info("Preencha o Perfil ou importe um currículo antes de continuar.")
            resume_id = ""
            strategy_label = "Padrão"
            prepare = False
    if prepare:
        strategy = "tailored" if strategy_label == "Direcionada" else "standard"
        for job in selected_jobs:
            repository.save_application(
                job.id, resume_id=resume_id, strategy=strategy, status="prepared"
            )
        flash(f"{len(selected_jobs)} vaga(s) pronta(s) para revisão.")
        st.switch_page("app_pages/applications.py")
