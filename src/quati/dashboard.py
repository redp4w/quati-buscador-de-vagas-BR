from __future__ import annotations

from pathlib import Path

import streamlit as st

from quati.ui import initialize_session, render_local_session_gate


def run() -> None:
    asset_dir = Path(__file__).with_name("assets")
    st.set_page_config(
        page_title="Q.U.A.T.I. · Vagas públicas BR",
        page_icon=str(asset_dir / "quati-icon.png"),
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.html(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            overflow-x: hidden;
            background:
                radial-gradient(circle at 88% 8%, rgba(255, 23, 56, .10), transparent 28rem),
                radial-gradient(circle at 18% 92%, rgba(168, 255, 96, .055), transparent 32rem),
                #060807;
        }
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 999999;
            pointer-events: none;
            opacity: .055;
            background: repeating-linear-gradient(
                0deg,
                rgba(255, 255, 255, .7) 0,
                rgba(255, 255, 255, .7) 1px,
                transparent 1px,
                transparent 4px
            );
        }
        [data-testid="stHeader"] {
            background: rgba(6, 8, 7, .86);
        }
        section[data-testid="stSidebar"] {
            overflow-x: hidden;
            box-shadow: 7px 0 24px rgba(255, 23, 56, .08);
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            overflow-x: hidden;
        }
        section[data-testid="stSidebar"][aria-expanded="true"]
        [data-testid="stSidebarHeader"] {
            min-height: 94px;
            align-items: flex-start;
            padding-top: 8px;
        }
        section[data-testid="stSidebar"][aria-expanded="true"]
        [data-testid="stLogoLink"] {
            display: block;
            width: 252px;
            height: 84px;
        }
        section[data-testid="stSidebar"][aria-expanded="true"]
        [data-testid="stSidebarLogo"] {
            width: 252px;
            max-width: 252px;
            height: 84px !important;
            max-height: 84px !important;
            border-radius: 0;
            object-fit: contain;
            filter: drop-shadow(0 0 12px rgba(255, 23, 56, .24));
        }
        h1, h2, h3 {
            letter-spacing: .045em;
            text-transform: uppercase;
            text-shadow: 2px 2px 0 rgba(255, 23, 56, .22);
        }
        [data-testid="stMetric"],
        [data-testid="stVerticalBlockBorderWrapper"] {
            box-shadow: inset 0 0 0 1px rgba(168, 255, 96, .035);
        }
        .stButton > button,
        .stFormSubmitButton > button,
        [data-testid="stLinkButton"] > a {
            letter-spacing: .035em;
            font-weight: 700;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.16), 3px 3px 0 #21060b;
        }
        .st-key-profile_gate {
            margin: 0;
            padding: 1rem 1.25rem;
            border: 1px solid #7A1022;
            background: linear-gradient(145deg, rgba(20, 26, 18, .96), rgba(5, 6, 5, .98));
            box-shadow: 10px 10px 0 rgba(24, 4, 8, .78), inset 0 0 28px rgba(168,255,96,.025);
        }
        .st-key-job_loading_overlay {
            position: fixed;
            inset: 0;
            z-index: 1000000;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
            background: rgba(3, 4, 3, .88);
            backdrop-filter: blur(3px);
        }
        .st-key-job_loading_content {
            text-align: center;
            filter: drop-shadow(0 0 18px rgba(255, 23, 56, .22));
        }
        .st-key-job_loading_content [data-testid="stImage"] {
            width: 320px !important;
            max-width: 82vw;
        }
        .st-key-job_loading_content [data-testid="stImage"] img {
            width: 320px;
            max-width: 82vw;
            height: auto;
        }
        </style>
        """
    )
    st.logo(
        str(asset_dir / "quati-menu-scan.gif"),
        size="large",
        icon_image=str(asset_dir / "quati-icon.png"),
        link="https://github.com/redp4w/quati-buscador-de-vagas-BR",
    )
    initialize_session()
    if not render_local_session_gate():
        return
    pages = {
        "": [
            st.Page("app_pages/home.py", title="Início", icon=":material/home:", default=True),
            st.Page("app_pages/jobs.py", title="Buscar vagas", icon=":material/search:"),
            st.Page(
                "app_pages/applications.py",
                title="Preparar candidatura",
                icon=":material/edit_document:",
            ),
            st.Page("app_pages/assistant.py", title="Assistente", icon=":material/assistant:"),
        ],
        "Meu perfil": [
            st.Page("app_pages/profile.py", title="Dados pessoais", icon=":material/person:"),
            st.Page("app_pages/resumes.py", title="Currículos", icon=":material/description:"),
        ],
        "Configurações": [
            st.Page(
                "app_pages/ai_settings.py",
                title="Inteligência artificial",
                icon=":material/model_training:",
            ),
            st.Page(
                "app_pages/job_sources.py",
                title="Adzuna e fontes",
                icon=":material/travel_explore:",
            ),
        ],
        "Acompanhamento": [
            st.Page(
                "app_pages/automation.py",
                title="Buscas agendadas",
                icon=":material/schedule:",
            ),
            st.Page(
                "app_pages/history.py",
                title="Histórico de vagas",
                icon=":material/history:",
            ),
            st.Page("app_pages/logs.py", title="Logs técnicos", icon=":material/terminal:"),
        ],
    }
    page = st.navigation(pages, position="sidebar")
    page.run()
