import streamlit as st

from quati.domain.job import safe_table_text
from quati.resumes import export_docx, resume_from_profile
from quati.ui import resume_vault, vault_passphrase
from quati.ui.context import flash, render_flash

vault = resume_vault()
render_flash()
st.header("Currículos")
st.caption("Guarde currículos prontos ou crie uma versão usando os dados do seu perfil.")

with st.form("resume_import", border=True):
    st.subheader("Importar currículo")
    label = st.text_input("Nome da versão")
    uploaded = st.file_uploader("Arquivo PDF ou DOCX", type=["pdf", "docx"])
    add = st.form_submit_button("Importar", type="primary", icon=":material/upload:")

if add:
    if uploaded is None:
        st.error("Selecione um arquivo PDF ou DOCX.")
    else:
        try:
            passphrase = vault_passphrase("resumes")
            vault.add(
                passphrase,
                label=label,
                filename=uploaded.name,
                content=uploaded.getvalue(),
            )
            st.session_state["resume_library"] = vault.load(passphrase)
            flash("Currículo importado.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

profile = st.session_state.get("candidate_profile")
if profile is not None:
    with st.form("resume_from_profile", border=True):
        st.subheader("Criar com os dados do perfil")
        generated_label = st.text_input("Nome da versão gerada", value="Currículo base")
        generate = st.form_submit_button("Gerar e guardar", icon=":material/add:")
    if generate:
        try:
            passphrase = vault_passphrase("resumes")
            document = resume_from_profile(profile)
            content = export_docx("Currículo", document.text)
            vault.add(
                passphrase,
                label=generated_label,
                filename=document.filename,
                content=content,
            )
            st.session_state["resume_library"] = vault.load(passphrase)
            flash("Currículo base gerado.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

resumes = st.session_state.get("resume_library")
if resumes is not None:
    st.subheader("Seus currículos")
    if not resumes:
        st.info("A biblioteca está vazia.")
    else:
        st.dataframe(
            [
                {
                    "Nome": safe_table_text(item.label),
                    "Arquivo": safe_table_text(item.filename),
                    "Importado": item.created_at.strftime("%d/%m/%Y %H:%M UTC"),
                }
                for item in resumes
            ],
            hide_index=True,
            key="resume_library_table",
        )
        labels = {f"{item.label} — {item.filename}": item for item in resumes}
        selected_label = st.selectbox("Currículo", list(labels), key="resume_selected")
        selected = labels[selected_label]
        with st.container(horizontal=True):
            st.download_button(
                "Baixar original",
                data=selected.content,
                file_name=selected.filename,
                mime=(
                    "application/pdf"
                    if selected.filename.lower().endswith(".pdf")
                    else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                icon=":material/download:",
            )

        with st.form("resume_delete", border=False):
            delete = st.form_submit_button("Excluir versão", icon=":material/delete:")
        if delete:
            try:
                passphrase = vault_passphrase("resumes")
                vault.delete(passphrase, selected.id)
                st.session_state["resume_library"] = vault.load(passphrase)
                flash("Currículo excluído da biblioteca.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
