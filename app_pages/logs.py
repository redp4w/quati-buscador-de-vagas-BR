import os
from datetime import datetime
from pathlib import Path

import streamlit as st

st.header("Logs técnicos")
st.caption(
    "Registros de diagnóstico do aplicativo. Para rever vagas encontradas, fontes consultadas "
    "e alterações nos anúncios, use Histórico de vagas."
)

# Log directory configuration
log_dir = Path("logs")
if not log_dir.exists():
    log_dir.mkdir(parents=True, exist_ok=True)

# Check for log files
log_files = list(log_dir.glob("*.log")) if log_dir.exists() else []

if not log_files:
    st.info("Nenhum arquivo de log encontrado.")
    st.caption("Os logs são gerados automaticamente durante o uso do aplicativo.")
else:
    # File selection
    selected_file = st.selectbox(
        "Selecione um arquivo de log",
        log_files,
        format_func=lambda x: x.name,
        index=0 if log_files else None,
    )
    
    if selected_file:
        try:
            with open(selected_file, encoding="utf-8", errors="ignore") as f:
                log_content = f.read()
            
            # Display options
            col1, col2 = st.columns([1, 1])
            with col1:
                show_full = st.checkbox("Mostrar log completo", value=False)
            with col2:
                filter_errors = st.checkbox("Filtrar apenas erros", value=False)
            
            # Process content
            lines = log_content.split("\n")
            
            if filter_errors:
                lines = [line for line in lines if "ERROR" in line or "error" in line.lower()]
            
            if not show_full:
                lines = lines[-100:]  # Show last 100 lines
            
            # Display log content
            st.text_area(
                "Conteúdo do log",
                value="\n".join(lines),
                height=400,
                key="log_content",
            )
            
            # Statistics
            with st.expander("Estatísticas do log"):
                total_lines = len(log_content.split("\n"))
                error_count = log_content.lower().count("error")
                warning_count = log_content.lower().count("warning")
                
                st.metric("Total de linhas", total_lines)
                col1, col2 = st.columns(2)
                col1.metric("Erros", error_count)
                col2.metric("Avisos", warning_count)
            
            # Download option
            st.download_button(
                "Baixar arquivo de log",
                log_content,
                file_name=selected_file.name,
                mime="text/plain",
            )
            
        except Exception as e:
            st.error(f"Erro ao ler arquivo de log: {str(e)}")

# Clear logs option
if st.button("Limpar logs antigos", icon=":material/delete:"):
    try:
        if log_dir.exists():
            for log_file in log_files:
                log_file.unlink()
            st.success("Logs antigos removidos.")
            st.rerun()
    except Exception as e:
        st.error(f"Erro ao limpar logs: {str(e)}")

# System information
with st.expander("Informações do sistema"):
    st.write(f"Data/hora atual: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.write(f"Diretório de logs: {log_dir.absolute()}")
    st.write(f"Arquivos de log: {len(log_files)}")
    st.write(f"Sistema operacional: {os.name}")
