import httpx
import streamlit as st

from quati.ai import AIService, build_ai_provider_registry
from quati.config import AIConfiguration, Settings
from quati.ui import ai_configuration_vault, vault_passphrase
from quati.ui.context import flash, render_flash

PROVIDER_DEFAULTS = {
    "none": ("", ""),
    "ollama": ("gemma3:1b", "http://127.0.0.1:11434"),
    "gemini": ("gemini-3.5-flash-lite", ""),
    "openai_compatible": ("local-model", "http://127.0.0.1:1234/v1"),
}
GEMINI_MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash"]

vault = ai_configuration_vault()
registry = build_ai_provider_registry()
st.session_state.setdefault("ai_form_version", 0)
render_flash()
st.header("Inteligência artificial")
st.caption(
    "Conecte o modelo que preferir. A compatibilidade e a geração dos arquivos continuam locais."
)

configuration = st.session_state.get("ai_configuration")
if configuration is None:
    try:
        configuration = AIConfiguration.from_settings(Settings())
    except ValueError:
        configuration = AIConfiguration()

modules = {module.name: module for module in registry.modules()}
active_module = modules.get(configuration.provider, modules["none"])
with st.container(border=True):
    st.subheader("Módulo ativo")
    st.write(f"**{active_module.label}** — {active_module.description}")
    if configuration.provider == "none":
        st.caption("Nenhuma IA generativa está configurada. A análise local continua disponível.")
    elif configuration.provider == "ollama":
        st.caption(f"Modelo local: {configuration.model}")
    else:
        consent_label = (
            "envio autorizado" if configuration.external_consent else "aguardando autorização"
        )
        st.caption(f"Modelo: {configuration.model} · {consent_label}")

st.session_state.setdefault("ai_provider_choice", configuration.provider)
provider = st.selectbox(
    "Escolher módulo",
    list(modules),
    key="ai_provider_choice",
    format_func=lambda name: modules[name].label,
)
if provider not in modules:
    st.error("Provedor inválido.")
    st.stop()
st.caption(modules[provider].description)

default_model, default_endpoint = PROVIDER_DEFAULTS[provider]
if configuration.provider == provider:
    default_model = configuration.model or default_model
    default_endpoint = configuration.endpoint or default_endpoint

form_version = st.session_state["ai_form_version"]
with st.form(f"ai_configuration_{provider}_{form_version}", border=True):
    model = ""
    endpoint = ""
    api_key = ""
    if provider == "ollama":
        model = st.text_input("Modelo", value=default_model, max_chars=200)
        endpoint = st.text_input("Endereço local", value=default_endpoint, max_chars=2_048)
        st.caption("Para economizar memória, experimente gemma3:1b (download de cerca de 815 MB).")
    elif provider == "gemini":
        options = list(dict.fromkeys([*GEMINI_MODELS, default_model]))
        model = st.selectbox(
            "Modelo",
            options,
            index=options.index(default_model),
            accept_new_options=True,
        )
        api_key = st.text_input(
            "Chave da API",
            type="password",
            max_chars=10_000,
            key=f"ai_api_key_{provider}_{form_version}",
        )
        st.warning(
            "No plano gratuito, o Google pode usar o conteúdo enviado para melhorar seus "
            "produtos. Só autorize o envio se você concordar com essa condição."
        )
    elif provider == "openai_compatible":
        model = st.text_input("Modelo", value=default_model, max_chars=200)
        endpoint = st.text_input("Endereço da API", value=default_endpoint, max_chars=2_048)
        api_key = st.text_input(
            "Chave opcional",
            type="password",
            max_chars=10_000,
            key=f"ai_api_key_{provider}_{form_version}",
        )
        st.caption("Endereços locais podem usar HTTP. Serviços externos precisam usar HTTPS.")

    st.subheader("Privacidade")
    st.caption(
        "Quando há um perfil salvo, o assistente usa esses dados como contexto. "
        "O envio externo depende da autorização abaixo."
    )
    external_consent = False
    if provider in {"gemini", "openai_compatible"}:
        external_consent = st.checkbox(
            "Autorizar envio ao provedor externo",
            value=configuration.external_consent,
            help=(
                "Autoriza mensagens, vagas e currículos quando a API configurada é externa. "
                "A preferência fica salva neste cofre e pode ser revogada aqui."
            ),
        )
    else:
        st.caption("Modelos locais processam o texto no endereço local configurado.")

    with st.container(horizontal=True):
        test = st.form_submit_button("Testar conexão", icon=":material/cable:")
        save = st.form_submit_button("Salvar configuração", type="primary", icon=":material/save:")

if provider in {"gemini", "openai_compatible"} and not api_key:
    if configuration.provider == provider:
        api_key = configuration.api_key

try:
    candidate = AIConfiguration(
        provider=provider,
        model=model,
        endpoint=endpoint,
        api_key=api_key,
        include_profile_context=True,
        external_consent=external_consent,
    )
except ValueError as exc:
    candidate = None
    if test or save:
        st.error(str(exc))

if test and candidate is not None:
    if provider == "none":
        st.success("Análise local ativa. Não há conexão para testar.")
    else:
        try:
            response = AIService(candidate.to_settings()).assist(
                "Responda somente com OK.", external_consent=True
            )
            st.success(f"Conexão funcionando: {response[:80]}")
        except (httpx.HTTPError, ValueError):
            st.error(
                "Não foi possível conectar. Confira endereço, modelo, chave e limite da conta."
            )

if save and candidate is not None:
    try:
        vault.save(candidate, vault_passphrase("ai"))
        st.session_state["ai_configuration"] = candidate
        st.session_state["assistant_messages"] = []
        st.session_state["application_bundle"] = None
        st.session_state["ai_form_version"] += 1
        flash("Configuração de IA salva.")
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))

if provider == "gemini":
    st.link_button(
        "Criar chave no Google AI Studio",
        "https://aistudio.google.com/app/apikey",
        icon=":material/open_in_new:",
    )
elif provider == "ollama":
    st.link_button(
        "Baixar Ollama para Windows",
        "https://ollama.com/download/windows",
        icon=":material/download:",
    )

st.info(
    "O modelo local de documento cuida do visual do currículo. A IA apenas sugere mudanças no "
    "texto e não executa o conteúdo recebido."
)

with st.expander("Módulos disponíveis e como adicionar outro"):
    st.markdown(
        "- **Análise local:** funciona sem modelo generativo.  \n"
        "- **Ollama:** precisa do aplicativo local, endereço e nome do modelo.  \n"
        "- **Gemini:** precisa do modelo, chave da API e autorização de envio.  \n"
        "- **API compatível:** precisa do endereço, modelo e, quando exigida, chave."
    )
    st.write(
        "Serviços com `/chat/completions` podem usar **API compatível com OpenAI**. "
        "Para outro protocolo, contribua com uma implementação de `TextGenerator` registrada "
        "como `AIProviderModule`."
    )
