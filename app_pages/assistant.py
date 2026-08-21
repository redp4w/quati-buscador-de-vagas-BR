import httpx
import streamlit as st

from quati.ai import AIService
from quati.domain.job import clean_text
from quati.ui import ai_configuration_vault, get_ai_settings

SUGGESTIONS = {
    "Revisar meu resumo": "Como posso deixar meu resumo profissional mais direto?",
    "Preparar entrevista": "Crie perguntas para eu treinar antes de uma entrevista.",
    "Melhorar palavras-chave": "Como escolher palavras-chave verdadeiras para meu currículo?",
}

st.header("Assistente")
with st.container(horizontal=True):
    st.page_link(
        "app_pages/resumes.py",
        label="Abrir biblioteca de currículos",
        icon=":material/folder_open:",
    )
    st.page_link(
        "app_pages/ai_settings.py",
        label="Configurar inteligência artificial",
        icon=":material/settings:",
    )
settings = get_ai_settings()
service = AIService(settings)

if settings.ai_provider == "none":
    message = (
        "Abra Inteligência artificial para escolher um modelo para o assistente."
        if ai_configuration_vault().exists()
        else "Configure um modelo em Inteligência artificial para usar o assistente."
    )
    st.info(message)
    st.stop()

model = {
    "ollama": settings.ollama_model,
    "gemini": settings.gemini_model,
    "openai_compatible": settings.openai_compatible_model,
}[settings.ai_provider]
st.caption(f"{service.provider_label()} · {model}. A conversa termina quando você fecha a sessão.")

profile = st.session_state.get("candidate_profile")
configuration = st.session_state.get("ai_configuration")
include_profile = profile is not None
external = service.requires_external_consent()
consent = not external or bool(configuration and configuration.external_consent)
provider_status = "envio autorizado" if consent else "envio não autorizado"
context_status = "perfil incluído automaticamente" if include_profile else "sem perfil salvo"
st.caption(f"{context_status} · {provider_status}.")
if external and not consent:
    st.warning("Autorize o provedor externo em Inteligência artificial para enviar mensagens.")

with st.container(horizontal=True, horizontal_alignment="right"):
    if st.button("Limpar conversa", icon=":material/delete_sweep:"):
        st.session_state["assistant_messages"] = []
        st.rerun()

messages = st.session_state.get("assistant_messages", [])[-20:]
for message in messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

suggested_prompt = None
if not messages:
    with st.container(border=True):
        st.caption("Sugestões rápidas — clique para usar")
        selected = st.pills(
            "Sugestões rápidas",
            list(SUGGESTIONS),
            label_visibility="collapsed",
        )
        if selected:
            suggested_prompt = SUGGESTIONS[selected]

prompt = st.chat_input(
    "",
    key="career_assistant_input",
    max_chars=4_000,
    disabled=external and not consent,
    submit_mode="disable",
    height=68,
)
prompt = prompt or suggested_prompt
if prompt:
    safe_prompt = clean_text(str(prompt), max_length=4_000)
    previous = "\n".join(f"{item['role']}: {item['content']}" for item in messages[-6:])
    profile_context = profile.text() if include_profile and profile is not None else ""
    context = f"{previous}\n{profile_context}".strip()
    st.session_state["assistant_messages"].append({"role": "user", "content": safe_prompt})
    with st.chat_message("user"):
        st.write(safe_prompt)
    try:
        with st.chat_message("assistant"):
            answer = service.assist(
                safe_prompt,
                context=context,
                external_consent=consent,
            )
            st.write(answer)
        st.session_state["assistant_messages"].append({"role": "assistant", "content": answer})
        st.session_state["assistant_messages"] = st.session_state["assistant_messages"][-20:]
    except ValueError as exc:
        st.error(str(exc))
    except httpx.HTTPError:
        st.error("O modelo não respondeu. Confira a configuração e o limite do provedor.")
