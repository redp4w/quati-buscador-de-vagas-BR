import streamlit as st

from quati.location import (
    BRAZILIAN_STATES,
    brazilian_cities,
    canonical_brazilian_location,
    split_brazilian_location,
)
from quati.profile import (
    JOB_LEVELS,
    WORK_MODES,
    CandidateProfile,
    preference_values,
)
from quati.resumes import extract_resume, profile_fields_from_resume
from quati.ui import profile_vault, reset_local_account, vault_passphrase
from quati.ui.context import flash, render_flash

PROFILE_FIELDS = tuple(CandidateProfile.__dataclass_fields__)
PROFILE_WIDGET_KEYS = {field: f"profile_field_{field}" for field in PROFILE_FIELDS}
SELECTION_WIDGET_KEYS = {
    "target_roles": "profile_preference_roles",
    "target_levels": "profile_preference_levels",
    "max_distance_km": "profile_preference_distance",
    "work_modes": "profile_preference_modes",
    "state": "profile_preference_state",
    "city": "profile_preference_city",
}
PROFILE_ONLY_FIELDS = {"job_portals", "preferred_location"}
STATE_LABELS = dict(BRAZILIAN_STATES)
st.session_state.setdefault("profile_import_version", 0)


def clear_profile_widgets() -> None:
    for key in (*PROFILE_WIDGET_KEYS.values(), *SELECTION_WIDGET_KEYS.values()):
        st.session_state.pop(key, None)


def clear_profile_city() -> None:
    """Evita manter uma cidade da UF anterior após a troca do estado."""
    st.session_state[SELECTION_WIDGET_KEYS["city"]] = ""


vault = profile_vault()
render_flash()
st.header("Perfil")
st.caption("Seus dados ficam neste computador. Você os desbloqueia uma vez por sessão.")

profile = st.session_state.get("candidate_profile")

values = {field: getattr(profile, field) for field in PROFILE_FIELDS} if profile else {}
text_fields = set(PROFILE_FIELDS) - set(SELECTION_WIDGET_KEYS) - PROFILE_ONLY_FIELDS
for field in text_fields:
    key = PROFILE_WIDGET_KEYS[field]
    st.session_state.setdefault(key, values.get(field, ""))
st.session_state.setdefault(
    SELECTION_WIDGET_KEYS["target_roles"], list(preference_values(values.get("target_roles", "")))
)
st.session_state.setdefault(
    SELECTION_WIDGET_KEYS["target_levels"],
    list(preference_values(values.get("target_levels", ""))),
)
st.session_state.setdefault(
    SELECTION_WIDGET_KEYS["max_distance_km"], int(values.get("max_distance_km", "80"))
)
st.session_state.setdefault(
    SELECTION_WIDGET_KEYS["work_modes"], list(preference_values(values.get("work_modes", "")))
)
profile_city, profile_state = split_brazilian_location(values.get("preferred_location", ""))
st.session_state.setdefault(SELECTION_WIDGET_KEYS["state"], profile_state)
st.session_state.setdefault(SELECTION_WIDGET_KEYS["city"], profile_city)

with st.expander(
    "Preencher dados automaticamente a partir de PDF ou DOCX",
    icon=":material/upload_file:",
):
    st.caption(
        "O arquivo é lido apenas na memória e não é armazenado. Confira os campos antes de salvar."
    )
    with st.form("profile_import", border=False):
        uploaded = st.file_uploader(
            "Currículo PDF ou DOCX",
            type=["pdf", "docx"],
            key=f"profile_import_file_{st.session_state['profile_import_version']}",
        )
        prefill = st.form_submit_button("Ler e preencher", icon=":material/upload_file:")

if prefill:
    if uploaded is None:
        st.error("Selecione um PDF ou DOCX.")
    else:
        try:
            extracted = profile_fields_from_resume(
                extract_resume(uploaded.name, uploaded.getvalue())
            )
            if not extracted:
                raise ValueError("Nenhum campo reconhecido. Preencha o perfil manualmente.")
            for field, value in extracted.items():
                st.session_state[PROFILE_WIDGET_KEYS[field]] = value
            st.session_state["profile_import_version"] += 1
            flash(f"{len(extracted)} campo(s) preenchido(s). Confira os dados antes de salvar.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

with st.container(border=True):
    st.subheader("Dados profissionais")
    name = st.text_input("Nome", key=PROFILE_WIDGET_KEYS["name"], max_chars=200)
    headline = st.text_input(
        "Título profissional", key=PROFILE_WIDGET_KEYS["headline"], max_chars=500
    )
    contact = st.columns(2)
    email = contact[0].text_input("E-mail", key=PROFILE_WIDGET_KEYS["email"], max_chars=320)
    phone = contact[1].text_input("Telefone", key=PROFILE_WIDGET_KEYS["phone"], max_chars=100)
    address = st.text_input("Endereço", key=PROFILE_WIDGET_KEYS["address"], max_chars=500)
    links = st.text_area("Links profissionais", key=PROFILE_WIDGET_KEYS["links"], height=80)
    summary = st.text_area("Resumo profissional", key=PROFILE_WIDGET_KEYS["summary"], height=120)
    skills = st.text_area("Competências", key=PROFILE_WIDGET_KEYS["skills"], height=120)
    projects = st.text_area("Projetos", key=PROFILE_WIDGET_KEYS["projects"], height=160)
    experience = st.text_area("Experiência", key=PROFILE_WIDGET_KEYS["experience"], height=220)
    education = st.text_area("Educação", key=PROFILE_WIDGET_KEYS["education"], height=140)
    certifications = st.text_area(
        "Certificações", key=PROFILE_WIDGET_KEYS["certifications"], height=100
    )
    languages = st.text_area("Idiomas", key=PROFILE_WIDGET_KEYS["languages"], height=80)
    additional = st.text_area("Diferenciais", key=PROFILE_WIDGET_KEYS["additional"], height=100)
    keywords = st.text_area("Palavras-chave ATS", key=PROFILE_WIDGET_KEYS["keywords"], height=80)
    st.subheader("Preferências de vagas")
    st.caption(
        "Essas preferências orientam a busca e a compatibilidade. Elas não entram no currículo."
    )
    role_options = list(st.session_state[SELECTION_WIDGET_KEYS["target_roles"]])
    target_roles = st.multiselect(
        "Cargos ou áreas de interesse",
        role_options,
        accept_new_options=True,
        max_selections=5,
        key=SELECTION_WIDGET_KEYS["target_roles"],
        placeholder="",
        help="Digite um cargo e pressione Enter. Cadastre até cinco.",
    )
    target_levels = st.pills(
        "Níveis aceitos",
        JOB_LEVELS,
        selection_mode="multi",
        key=SELECTION_WIDGET_KEYS["target_levels"],
    )
    location_columns = st.columns([1, 2, 1])
    preferred_state = location_columns[0].selectbox(
        "Estado",
        ("", *STATE_LABELS),
        format_func=lambda value: f"{value} — {STATE_LABELS[value]}" if value else "",
        key=SELECTION_WIDGET_KEYS["state"],
        on_change=clear_profile_city,
    )
    city_options = brazilian_cities(preferred_state) if preferred_state else ()
    preferred_city = location_columns[1].selectbox(
        "Cidade-base",
        ("", *city_options),
        key=SELECTION_WIDGET_KEYS["city"],
        disabled=not preferred_state,
    )
    max_distance_km = location_columns[2].number_input(
        "Raio máximo (km)",
        min_value=1,
        max_value=500,
        step=5,
        key=SELECTION_WIDGET_KEYS["max_distance_km"],
    )
    work_modes = st.pills(
        "Modalidades aceitas",
        WORK_MODES,
        selection_mode="multi",
        key=SELECTION_WIDGET_KEYS["work_modes"],
    )
    save = st.button("Salvar perfil", type="primary", icon=":material/save:")

if save:
    try:
        updated = CandidateProfile(
            name=name,
            email=email,
            phone=phone,
            address=address,
            skills=skills,
            education=education,
            experience=experience,
            headline=headline,
            summary=summary,
            languages=languages,
            certifications=certifications,
            links=links,
            projects=projects,
            additional=additional,
            keywords=keywords,
            target_roles="; ".join(target_roles),
            target_levels="; ".join(target_levels),
            preferred_location=canonical_brazilian_location(
                preferred_city,
                preferred_state,
            ),
            max_distance_km=str(max_distance_km),
            work_modes="; ".join(work_modes),
        )
        vault.save(updated, vault_passphrase("profile"))
        st.session_state["candidate_profile"] = updated
        for key in (
            "job_search_roles",
            "job_search_levels",
            "job_search_modes",
            "job_search_state",
            "job_search_city",
            "job_search_automatic_sources",
            "job_search_assisted_sources",
            "job_search_keywords",
            "active_job_search_request",
        ):
            st.session_state.pop(key, None)
        flash("Perfil salvo.")
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))

st.divider()
with st.expander("Apagar dados locais e começar do zero"):
    st.warning(
        "Esta opção apaga perfil, currículos, configurações, vagas, histórico, candidaturas, "
        "alertas e agendamentos deste computador. Não é possível desfazer."
    )
    with st.form("factory_reset", border=False):
        reset_phrase = st.text_input(
            "Digite LIMPAR para confirmar",
            max_chars=10,
            autocomplete="off",
        )
        reset_confirmed = st.checkbox("Entendo que todos os dados locais serão apagados")
        reset = st.form_submit_button(
            "Apagar dados locais",
            icon=":material/delete_forever:",
        )

if reset:
    if reset_phrase != "LIMPAR" or not reset_confirmed:
        st.error("Digite LIMPAR e marque a confirmação.")
    else:
        try:
            reset_local_account()
            st.cache_data.clear()
            st.cache_resource.clear()
            st.session_state.clear()
            st.rerun()
        except (OSError, ValueError) as exc:
            st.error(f"Não foi possível limpar os dados locais: {exc}")
