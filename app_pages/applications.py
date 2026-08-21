import streamlit as st

from quati.ai import AIService, ResumeSuggestions, analyze_locally
from quati.resumes import (
    build_external_resume_prompt,
    create_cover_letter,
    export_docx,
    export_html,
    export_pdf,
    resume_from_profile,
    resume_section_titles,
)
from quati.ui import get_ai_settings, get_repository
from quati.ui.context import flash, render_flash

TEMPLATES = {
    "Moderno": "modern",
    "Clássico": "classic",
    "Minimalista": "minimal",
    "Contemporâneo": "contemporary",
    "Executivo": "executive",
}
ACCENTS = {
    "Vermelho": "red",
    "Azul-marinho": "navy",
    "Grafite": "graphite",
    "Verde": "forest",
    "Vinho": "wine",
}
DENSITIES = {"Confortável": "comfortable", "Compacto": "compact"}

repository = get_repository()
render_flash()
st.subheader("Ajuste o currículo para a vaga escolhida")
st.caption("Revise o conteúdo, baixe os arquivos e conclua a candidatura no portal original.")

applications = repository.list_applications()
if not applications:
    st.info("Selecione uma vaga em Vagas e escolha Preparar para aplicar.")
    st.stop()

jobs = {item.job_id: repository.get_job(item.job_id) for item in applications}
st.caption(f"{len(applications)} vaga(s) em preparação")
for item in applications:
    selected_job = jobs[item.job_id]
    with st.container(
        border=True,
        horizontal=True,
        vertical_alignment="center",
        horizontal_alignment="distribute",
    ):
        st.markdown(f"**{selected_job.title}**  \n{selected_job.company}")
        st.link_button(
            ":material/open_in_new:",
            selected_job.url,
            help="Abrir anúncio original",
        )
        if st.button(
            ":material/delete:",
            key=f"remove_prepared_{item.id}",
            help="Remover da preparação",
        ):
            repository.delete_application(item.id)
            active_bundle = st.session_state.get("application_bundle") or {}
            if active_bundle.get("application_id") == item.id:
                st.session_state["application_bundle"] = None
            flash("Vaga removida da preparação.")
            st.rerun()

labels = {
    f"{jobs[item.job_id].title} - {jobs[item.job_id].company} (#{item.id})": item
    for item in applications
}
application = labels[st.selectbox("Currículo para", list(labels))]
job = jobs[application.job_id]

resume = None
if application.resume_id == "profile":
    profile = st.session_state.get("candidate_profile")
    if profile is not None:
        resume = resume_from_profile(profile)
else:
    resumes = st.session_state.get("resume_library") or []
    stored = next((item for item in resumes if item.id == application.resume_id), None)
    if stored is not None:
        resume = stored.as_document()

if resume is None:
    st.warning("Abra o perfil ou o currículo escolhido para poder gerar os arquivos.")
else:
    service = AIService(get_ai_settings())
    provider_enabled = service.settings.ai_provider != "none"
    with st.form("application_prepare", border=True):
        st.subheader("Preparar currículo")
        st.write(f"Assistente: **{service.provider_label()}**")
        use_ai = st.checkbox(
            "Pedir sugestões de texto à IA",
            value=application.strategy == "tailored" and provider_enabled,
            disabled=not provider_enabled,
            help="A IA mostra sugestões separadas. Ela não altera o currículo nem gera o PDF.",
        )
        configuration = st.session_state.get("ai_configuration")
        consent = not service.requires_external_consent() or bool(
            configuration and configuration.external_consent
        )
        if use_ai and service.requires_external_consent() and not consent:
            st.warning(
                "Autorize o envio externo em Perfil → Inteligência artificial antes de usar a IA."
            )
        prepare = st.form_submit_button(
            "Analisar e preparar", type="primary", icon=":material/rate_review:"
        )
    if prepare:
        try:
            with st.spinner("Analisando currículo e vaga..."):
                analysis = analyze_locally(job, resume.text)
                suggestions = (
                    service.suggest_resume_text(job, resume.text, external_consent=consent)
                    if use_ai
                    else ResumeSuggestions("", (), (), ())
                )
                editor_key = f"resume_editor_{application.id}"
                letter_key = f"cover_letter_editor_{application.id}"
                st.session_state[editor_key] = resume.text
                st.session_state[letter_key] = create_cover_letter(resume, job)
                st.session_state["application_bundle"] = {
                    "application_id": application.id,
                    "analysis": analysis,
                    "suggestions": suggestions,
                    "editor_key": editor_key,
                    "letter_key": letter_key,
                    "pdf": None,
                    "docx": None,
                    "html": None,
                }
            st.success("Revisão pronta.")
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("A IA não respondeu. Verifique a configuração e tente novamente.")

    external_prompt = build_external_resume_prompt(resume, job)
    with st.expander("Prompt do currículo — use onde quiser"):
        st.caption(
            "O prompt remove nome e contatos. Revise antes de copiá-lo para uma ferramenta externa."
        )
        st.text_area("Prompt externo", external_prompt, height=220)
        st.download_button(
            "Baixar prompt",
            data=external_prompt.encode("utf-8"),
            file_name="prompt-revisao-curriculo.txt",
            mime="text/plain",
            icon=":material/download:",
        )

bundle = st.session_state.get("application_bundle")
if bundle and bundle.get("application_id") == application.id:
    analysis = bundle["analysis"]
    suggestions = bundle["suggestions"]
    with st.container(horizontal=True):
        st.metric("Compatibilidade local", f"{analysis.compatibility_score}%", border=True)
        st.metric("Requisitos", len(analysis.requirements), border=True)
        st.metric("Termos a conferir", len(analysis.missing_keywords), border=True)

    suggestion_values = (
        suggestions.summary,
        suggestions.highlights,
        suggestions.keywords,
        suggestions.warnings,
    )
    if any(suggestion_values):
        with st.container(border=True):
            st.subheader("Sugestões da IA")
            st.caption("Você decide quais sugestões aproveitar no currículo.")
            if suggestions.summary:
                st.write("Resumo sugerido:", suggestions.summary)
            for highlight in suggestions.highlights:
                st.text(f"• {highlight}")
            if suggestions.keywords:
                st.write("Palavras-chave para conferir:", ", ".join(suggestions.keywords))
            for warning in suggestions.warnings:
                st.warning(warning)

    resume_text = st.text_area(
        "Conteúdo do currículo",
        height=360,
        key=bundle["editor_key"],
        help="Edite somente informações verdadeiras. O PDF usa exatamente este texto.",
    )
    available_sections = resume_section_titles(resume_text)
    section_key = f"resume_sections_{application.id}"
    current_sections = st.session_state.get(section_key, list(available_sections))
    current_sections = [item for item in current_sections if item in available_sections]
    st.session_state[section_key] = current_sections or list(available_sections)

    st.subheader("Organização e visual")
    layout_columns = st.columns(3)
    template_label = layout_columns[0].selectbox(
        "Modelo", list(TEMPLATES), key=f"resume_template_{application.id}"
    )
    density_label = layout_columns[1].selectbox(
        "Densidade", list(DENSITIES), key=f"resume_density_{application.id}"
    )
    accent_label = layout_columns[2].selectbox(
        "Cor", list(ACCENTS), key=f"resume_accent_{application.id}"
    )
    section_order = st.multiselect(
        "Seções e ordem",
        list(available_sections),
        key=section_key,
        placeholder="",
        help="Remova uma seção para ocultá-la. Remova e selecione novamente para movê-la ao final.",
    )
    if not section_order:
        st.warning("Selecione ao menos uma seção.")
    show_preview = st.toggle(
        "Mostrar pré-visualização",
        value=False,
        key=f"resume_preview_{application.id}",
    )
    export_options = {
        "template": TEMPLATES[template_label],
        "density": DENSITIES[density_label],
        "accent": ACCENTS[accent_label],
        "section_order": tuple(section_order),
    }
    if show_preview and section_order:
        try:
            preview = export_html("Currículo", resume_text, **export_options)
            # O template escapa todos os dados e não contém JavaScript ou recursos externos.
            st.iframe(preview, height=720)
        except ValueError as exc:
            st.error(str(exc))

    st.subheader("Carta de apresentação e resumo profissional")
    st.caption(
        "A carta usa apenas informações encontradas no currículo. Revise o texto antes de enviar."
    )
    cover_letter = st.text_area(
        "Carta para a empresa",
        height=220,
        key=bundle["letter_key"],
    )
    if st.button(
        "Gerar HTML, PDF e DOCX",
        type="primary",
        icon=":material/description:",
        disabled=not section_order,
    ):
        try:
            with st.status("Gerando arquivos localmente...", expanded=False) as status:
                bundle["html"] = export_html("Currículo", resume_text, **export_options)
                bundle["pdf"] = export_pdf("Currículo", resume_text, **export_options)
                bundle["docx"] = export_docx("Currículo", resume_text)
                bundle["cover_letter"] = cover_letter
                status.update(label="Arquivos prontos", state="complete")
        except ValueError as exc:
            st.error(str(exc))

    if bundle.get("html") and bundle.get("pdf") and bundle.get("docx"):
        with st.container(horizontal=True):
            st.download_button(
                "Baixar HTML",
                data=bundle["html"].encode("utf-8"),
                file_name="curriculo-direcionado.html",
                mime="text/html",
                icon=":material/download:",
            )
            st.download_button(
                "Baixar PDF",
                data=bundle["pdf"],
                file_name="curriculo-direcionado.pdf",
                mime="application/pdf",
                icon=":material/download:",
            )
            st.download_button(
                "Baixar DOCX",
                data=bundle["docx"],
                file_name="curriculo-direcionado.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                icon=":material/download:",
            )
