import io
import json
import os
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import pyperclip
import streamlit as st

from core.client_db import (
    delete_client_contact,
    get_all_contacts,
    get_client_contact,
    get_db_path,
    save_client_contact,
    sync_from_central_de_erros,
)
from core.excel_reader import get_sheet_names, read_excel_smart
from core.message_builder import build_all_messages
from core.pdf_generator import generate_pdf_report
from core.processor import process_dataframe
from core.template_manager import load_templates, save_templates
from core.validator import validate_columns
from core.whatsapp_desktop import open_group_in_whatsapp_desktop

# Configuração da Página
st.set_page_config(
    page_title="Central de Certificados",
    page_icon="🛡",
    layout="wide"
)

# ── Design System ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, .stApp, [class*="css"] { font-family: 'Inter', sans-serif !important; }

    /* ── Background ─────────────────────────────────────────────── */
    .stApp {
        background:
            radial-gradient(ellipse 80% 55% at 50% -5%, rgba(79,70,229,0.20) 0%, transparent 60%),
            linear-gradient(180deg, #060c1a 0%, #080d1e 100%) !important;
        background-attachment: fixed !important;
    }

    /* ── App Header ─────────────────────────────────────────────── */
    .app-header {
        display: flex; align-items: center; gap: 16px;
        padding: 18px 24px; margin-bottom: 10px;
        background: rgba(10, 16, 35, 0.75);
        backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(99,102,241,0.16); border-radius: 16px;
        box-shadow: 0 8px 40px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.05);
    }
    .app-header-logo {
        display: flex; align-items: center; justify-content: center;
        width: 48px; height: 48px; border-radius: 13px; flex-shrink: 0;
        background: linear-gradient(135deg, #4338ca 0%, #7c3aed 100%);
        box-shadow: 0 4px 20px rgba(99,102,241,0.50);
    }
    .app-header-title {
        font-size: 1.4rem; font-weight: 800; letter-spacing: -0.5px; margin: 0 0 3px;
        background: linear-gradient(120deg, #e0e7ff 0%, #a5b4fc 50%, #c084fc 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .app-header-subtitle { font-size: 0.82rem; color: #475569; margin: 0; }
    .app-header-pill {
        margin-left: auto; display: flex; align-items: center; gap: 6px;
        padding: 5px 13px; border-radius: 999px;
        background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.22);
        font-size: 0.75rem; font-weight: 700; color: #34d399; white-space: nowrap;
        letter-spacing: 0.4px;
    }

    /* ── Metric Cards ────────────────────────────────────────────── */
    .metric-card {
        background: rgba(13,19,38,0.82); backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(99,102,241,0.18); border-radius: 14px;
        padding: 16px 18px; text-align: center;
        box-shadow: 0 4px 24px rgba(0,0,0,0.35);
        transition: transform 0.18s ease, border-color 0.18s ease;
    }
    .metric-card:hover { border-color: rgba(139,92,246,0.45); transform: translateY(-2px); }
    .metric-value       { font-size: 1.9rem; font-weight: 800; color: #818cf8; line-height: 1.1; }
    .metric-value-ok    { font-size: 1.9rem; font-weight: 800; color: #34d399; line-height: 1.1; }
    .metric-value-warn  { font-size: 1.9rem; font-weight: 800; color: #fbbf24; line-height: 1.1; }
    .metric-value-alert { font-size: 1.9rem; font-weight: 800; color: #f87171; line-height: 1.1; }
    .metric-label {
        font-size: 0.72rem; color: #475569; text-transform: uppercase;
        letter-spacing: 0.8px; font-weight: 700; margin-top: 5px;
    }

    /* ── Section headings ────────────────────────────────────────── */
    .section-heading {
        display: flex; align-items: center; gap: 10px;
        font-size: 0.97rem; font-weight: 700; color: #cbd5e1;
        margin: 22px 0 12px; letter-spacing: -0.1px;
    }
    .section-heading .sh-icon {
        display: flex; align-items: center; justify-content: center;
        width: 28px; height: 28px; border-radius: 8px;
        background: rgba(99,102,241,0.14); border: 1px solid rgba(99,102,241,0.24);
        flex-shrink: 0;
    }

    /* ── Expanders ───────────────────────────────────────────────── */
    .stApp div[data-testid="stExpander"] {
        background: rgba(10,15,30,0.72) !important;
        backdrop-filter: blur(12px);
        border: 1px solid rgba(99,102,241,0.17) !important;
        border-radius: 13px !important; margin-bottom: 10px !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.28);
    }

    /* ── Status Badges ───────────────────────────────────────────── */
    .status-badge {
        display: inline-flex; align-items: center; gap: 5px;
        font-size: 0.74rem; font-weight: 600; padding: 3px 9px;
        border-radius: 6px; margin-right: 5px; letter-spacing: 0.1px;
    }
    .badge-expired  { background: rgba(239,68,68,0.10); color: #fca5a5; border: 1px solid rgba(239,68,68,0.28); }
    .badge-warning  { background: rgba(245,158,11,0.10); color: #fcd34d; border: 1px solid rgba(245,158,11,0.28); }
    .badge-info     { background: rgba(59,130,246,0.10); color: #93c5fd; border: 1px solid rgba(59,130,246,0.28); }
    .badge-neutral  { background: rgba(100,116,139,0.12); color: #94a3b8; border: 1px solid rgba(100,116,139,0.25); }

    /* ── Textarea ────────────────────────────────────────────────── */
    div[data-baseweb="textarea"] textarea {
        background: rgba(6,10,24,0.96) !important; color: #e2e8f0 !important;
        border: 1px solid rgba(99,102,241,0.22) !important; border-radius: 10px !important;
        font-family: 'Cascadia Code','Fira Code','JetBrains Mono',monospace !important;
        font-size: 0.87rem !important; line-height: 1.58 !important;
    }

    /* ── Tab bar ─────────────────────────────────────────────────── */
    button[data-baseweb="tab"] { font-weight: 600 !important; font-size: 0.85rem !important; }

    /* ── Dividers & Scrollbar ────────────────────────────────────── */
    hr { border: none !important; border-top: 1px solid rgba(99,102,241,0.10) !important; margin: 18px 0 !important; }
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.28); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,0.50); }
    </style>
    """,
    unsafe_allow_html=True
)

# ── Paleta de ícones SVG ──────────────────────────────────────────────────────
class _SafeIconDict(dict):
    def __missing__(self, key):
        return ""

_ICON = _SafeIconDict({
    "shield":   '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#c4b5fd" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10" stroke="#a5b4fc" stroke-width="2.2"/></svg>',
    "msg":      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    "send":     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
    "phone":    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18" stroke-width="2.5"/></svg>',
    "gear":     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    "info":     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    "building": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="1"/><path d="M9 22V12h6v10"/><path d="M8 7h.01M12 7h.01M16 7h.01M8 11h.01M16 11h.01"/></svg>',
    "calendar": '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    "hash":     '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>',
    "list":     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>',
    "check":    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    "clock":    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    "wa":       '<svg width="14" height="14" viewBox="0 0 24 24" fill="#34d399"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z"/></svg>',
    "copy":     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    "edit":     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    "pdf":      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
    "sync":     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>',
    "search":   '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    "trash":    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>',
    "plus":     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
    "chart":    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
    "link":     '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
})

# Inicializa Session State para templates e controle de envios
if "templates" not in st.session_state:
    st.session_state.templates = load_templates()
if "enviados" not in st.session_state:
    st.session_state.enviados = {}

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="app-header">
        <div class="app-header-logo">{_ICON["shield"]}</div>
        <div style="flex:1;min-width:0">
            <div class="app-header-title">Central de Certificados</div>
            <div class="app-header-subtitle">Automação de conferência e cobrança de certificados digitais por conta e data de vencimento</div>
        </div>
        <div class="app-header-pill">
            <svg width="7" height="7" viewBox="0 0 10 10"><circle cx="5" cy="5" r="5" fill="#34d399"/></svg>
            Ativo
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ── Abas ──────────────────────────────────────────────────────────────────────
tab_mensagens, tab_grupos = st.tabs([
    "Mensagens",
    "WhatsApp",
])

with tab_mensagens:
    col_up, col_info = st.columns([2, 1])

    with col_up:
        uploaded_file = st.file_uploader(
            "Carregar Planilha Excel (.xlsx, .xls)",
            type=["xlsx", "xls"],
            help="Selecione a planilha contendo as informações de certificados."
        )

    if uploaded_file is not None:
        # Reseta os envios se uma planilha diferente for carregada
        file_signature = f"{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get("last_uploaded_signature") != file_signature:
            st.session_state.last_uploaded_signature = file_signature
            st.session_state.enviados = {}

        try:
            available_sheets = get_sheet_names(uploaded_file)
        except Exception as e:
            st.error(f"❌ Erro ao ler as abas da planilha: {e}")
            available_sheets = []

        selected_sheet = None
        if len(available_sheets) > 1:
            # Encontra a melhor aba preliminarmente
            try:
                _, best_sheet, _, _, _, _ = read_excel_smart(uploaded_file)
                default_index = available_sheets.index(best_sheet) if best_sheet in available_sheets else 0
            except Exception:
                default_index = 0

            with col_info:
                selected_sheet = st.selectbox(
                    "Selecione a Aba da Planilha:",
                    available_sheets,
                    index=default_index,
                    help="Esta pasta de trabalho possui mais de uma aba. O sistema selecionou automaticamente a mais compatível."
                )
        elif len(available_sheets) == 1:
            selected_sheet = available_sheets[0]

        if selected_sheet:
            try:
                df_mapped, sheet_used, h_row_used, matched_cols, missing_cols, _ = read_excel_smart(
                    uploaded_file, sheet_name=selected_sheet
                )
            except Exception as e:
                st.error(f"Erro ao ler a planilha: {e}")
                df_mapped = None
                missing_cols = ["Erro na leitura"]

            if df_mapped is not None:
                if missing_cols:
                    st.error(
                        f"**Colunas Obrigatórias Ausentes na aba '{selected_sheet}'!**\n\n"
                        f"As seguintes colunas não foram identificadas:\n\n"
                        + "\n".join([f"- `{col}`" for col in missing_cols])
                        + "\n\n**Colunas encontradas nesta aba:**\n"
                        + ", ".join([f"`{c}`" for c in df_mapped.columns if not str(c).startswith("Unnamed")])
                    )
                    if len(available_sheets) > 1:
                        st.info("Como o seu arquivo possui várias abas, você pode selecionar outra aba no campo acima.")
                else:
                    if len(available_sheets) > 1 or h_row_used > 0:
                        st.caption(f"Aba ativa: **{sheet_used}** (Cabeçalho detectado na linha {h_row_used + 1})")

                    # Processamento
                    result = process_dataframe(df_mapped, st.session_state.templates)
                    mensagens = build_all_messages(result.grupos, st.session_state.templates)

                    # Sincroniza estado de mensagens enviadas
                    for msg in mensagens:
                        m_key = msg['nome_conta']
                        w_key = f"chk_env_{msg['id']}"
                        if w_key in st.session_state:
                            st.session_state.enviados[m_key] = st.session_state[w_key]
                        elif m_key not in st.session_state.enviados:
                            st.session_state.enviados[m_key] = False

                    total_enviados = sum(
                        1 for msg in mensagens
                        if st.session_state.enviados.get(msg['nome_conta'], False)
                    )

                    # Cards de Métricas
                    st.markdown("---")
                    m4, m6 = st.columns(2)

                    with m4:
                        st.markdown(
                            f"""
                            <div class="metric-card">
                                <div class="metric-icon">{_ICON["msg"]}</div>
                                <div class="metric-value">{result.total_mensagens}</div>
                                <div class="metric-label">Mensagens Geradas</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with m6:
                        metric_enviados_class = "metric-value-ok" if (total_enviados == len(mensagens) and len(mensagens) > 0) else "metric-value"
                        st.markdown(
                            f"""
                            <div class="metric-card">
                                <div class="metric-icon">{_ICON["send"]}</div>
                                <div class="{metric_enviados_class}">{total_enviados} / {len(mensagens)}</div>
                                <div class="metric-label">Mensagens Enviadas</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    if mensagens:
                        progresso = total_enviados / len(mensagens)
                        st.progress(
                            progresso,
                            text=f"Progresso de envios: {total_enviados} de {len(mensagens)} concluídos ({int(progresso * 100)}%)"
                        )



                    # Alertas de Status Desconhecidos
                    if result.status_desconhecidos:
                        st.warning(
                            "**Status Não Configurados Encontrados na Planilha!**\n\n"
                            "Os seguintes valores de status não possuem template configurado:\n\n"
                            + "\n".join([f"- `{st_desc}`" for st_desc in result.status_desconhecidos])
                            + "\n\n*Entre em contato com o suporte para configurar novos templates para esses status.*"
                        )

                    # Alertas de Registros Incompletos / Problemáticos
                    if result.registros_problematicos:
                        with st.expander(f"{len(result.registros_problematicos)} Registros com Dados Incompletos / Inválidos (clique para ver)", expanded=False):

                            st.caption("Estes registros foram desconsiderados na geração de mensagens para evitar envio incompleto. Corrija na planilha original:")
                            df_prob = pd.DataFrame([
                                {
                                    "Linha": p["linha"],
                                    "Conta": p["nome_conta"],
                                    "Empresa": p["empresa"],
                                    "CNPJ": p["cnpj"],
                                    "Status": p["status"],
                                    "Problemas Identificados": ", ".join(p["motivos"])
                                }
                                for p in result.registros_problematicos
                            ])
                            st.dataframe(df_prob, use_container_width=True)


                    st.markdown(
                        f'<div class="section-heading"><div class="sh-icon">{_ICON["list"]}</div>Mensagens Prontas para Envio</div>',
                        unsafe_allow_html=True
                    )

                    if not mensagens:
                        st.info("Nenhuma mensagem precisou ser gerada. Todos os registros estão como 'CERTIFICADO OK' ou foram desconsiderados.")
                    else:
                        # Barra de Ferramentas: Filtros e Ações
                        col_busca, col_filtro_status, col_filtro_envio = st.columns([2.5, 2, 1.8])

                        with col_busca:
                            termo_busca = st.text_input("Buscar por Nome da Conta ou Empresa:", placeholder="Digite para filtrar...")

                        with col_filtro_status:
                            all_statuses = set()
                            for m in mensagens:
                                for s in m.get("statuses", [m["status"]]):
                                    all_statuses.add(s)
                            opcoes_status = ["Todos"] + sorted(list(all_statuses))
                            status_selecionado = st.selectbox("Filtrar por Status:", opcoes_status)

                        with col_filtro_envio:
                            filtro_envio = st.selectbox("Status de Envio:", ["Todos", "Apenas Pendentes", "Apenas Enviados"], index=0)

                        # Filtragem
                        mensagens_filtradas = mensagens
                        if termo_busca:
                            t = termo_busca.lower()
                            mensagens_filtradas = [
                                m for m in mensagens_filtradas
                                if t in m["nome_conta"].lower()
                                or any(t in it["empresa"].lower() or t in it["cnpj"].lower() for it in m["itens"])
                            ]

                        if status_selecionado != "Todos":
                            mensagens_filtradas = [
                                m for m in mensagens_filtradas
                                if status_selecionado in m.get("statuses", [m["status"]])
                            ]

                        if filtro_envio == "Apenas Pendentes":
                            mensagens_filtradas = [
                                m for m in mensagens_filtradas
                                if not st.session_state.enviados.get(m["nome_conta"], False)
                            ]
                        elif filtro_envio == "Apenas Enviados":
                            mensagens_filtradas = [
                                m for m in mensagens_filtradas
                                if st.session_state.enviados.get(m["nome_conta"], False)
                            ]

                        pendentes_count = len(mensagens) - total_enviados
                        st.caption(
                            f"Exibindo **{len(mensagens_filtradas)}** de **{len(mensagens)}** mensagens geradas "
                            f"(**{total_enviados}** enviada{'s' if total_enviados != 1 else ''}, "
                            f"**{pendentes_count}** pendente{'s' if pendentes_count != 1 else ''})."
                        )

                        # Renderização das Mensagens
                        for idx, msg in enumerate(mensagens_filtradas, start=1):
                            msg_key = msg["nome_conta"]
                            is_enviado = st.session_state.enviados.get(msg_key, False)

                            contact_info = get_client_contact(msg["nome_conta"])
                            nome_grupo_alvo = contact_info.get("contact_value", "") if contact_info else ""

                            # Badges dinâmicas para todos os status presentes no cliente
                            badges_status_html = ""
                            statuses_list = msg.get("statuses", [msg["status"]])
                            for st_item in statuses_list:
                                st_upper = st_item.upper()
                                st_badge_class = "badge-neutral"
                                if "EXPIRADO" in st_upper:
                                    st_badge_class = "badge-expired"
                                elif "5 DIAS" in st_upper or "HOJE" in st_upper:
                                    st_badge_class = "badge-warning"
                                elif "15 DIAS" in st_upper or "30 DIAS" in st_upper:
                                    st_badge_class = "badge-info"
                                badges_status_html += f'<span class="status-badge {st_badge_class}">Status: {st_item}</span> '

                            venc_card = "Datas diferentes" if msg.get("tem_datas_diferentes") else msg["data_expiracao"]
                            if is_enviado:
                                titulo_card = f"[ENVIADO]  {msg['nome_conta']}"
                            else:
                                titulo_card = msg['nome_conta']

                            with st.expander(titulo_card, expanded=not is_enviado):
                                badge_enviado_html = (
                                    f'<span class="status-badge" style="background:rgba(16,185,129,0.12);color:#34d399;border:1px solid rgba(16,185,129,0.30);">{_ICON["check"]} ENVIADO</span>'
                                    if is_enviado
                                    else ''
                                )

                                st.markdown(
                                    f'<div style="margin-bottom: 8px;">{badge_enviado_html}{badges_status_html}<span class="status-badge badge-neutral">Vencimento: {venc_card}</span></div>',
                                    unsafe_allow_html=True
                                )

                                st.text_area(
                                    label="Texto da Mensagem:",
                                    value=msg["mensagem"],
                                    height=240,
                                    key=f"txt_msg_{msg['id']}"
                                )

                                if contact_info and contact_info.get("contact_type") == "group_name":
                                    col_wa, col_cp, col_chk = st.columns([1.5, 1.1, 1.2])
                                    with col_wa:
                                        if st.button(
                                            "Abrir no WhatsApp",
                                            key=f"btn_wa_{msg['id']}",
                                            type="primary",
                                            use_container_width=True,
                                            help=f"Abre o WhatsApp Desktop no grupo '{nome_grupo_alvo}' e cola esta mensagem na caixa de envio",
                                        ):
                                            with st.spinner(f"Localizando '{nome_grupo_alvo}' no WhatsApp..."):
                                                ok_wa, msg_wa = open_group_in_whatsapp_desktop(nome_grupo_alvo, msg["mensagem"])
                                                if ok_wa:
                                                    st.session_state.enviados[msg_key] = True
                                                    st.session_state[f"chk_env_{msg['id']}"] = True
                                                    st.toast(msg_wa, icon="✅")
                                                    st.rerun()
                                                else:
                                                    st.error(msg_wa)

                                    with col_cp:
                                        if st.button("Copiar", key=f"btn_copy_{msg['id']}", use_container_width=True):
                                            pyperclip.copy(msg["mensagem"])
                                            st.toast(f"Mensagem de '{msg['nome_conta']}' copiada!", icon="✅")

                                    with col_chk:
                                        enviado_check = st.checkbox(
                                            "Marcar como enviado",
                                            value=is_enviado,
                                            key=f"chk_env_{msg['id']}"
                                        )
                                        if enviado_check != is_enviado:
                                            st.session_state.enviados[msg_key] = enviado_check
                                            st.rerun()

                                else:
                                    col_cp, col_chk = st.columns([1.2, 1.8])
                                    with col_cp:
                                        if st.button("Copiar Mensagem", key=f"btn_copy_{msg['id']}", use_container_width=True):
                                            pyperclip.copy(msg["mensagem"])
                                            st.toast(f"Mensagem de '{msg['nome_conta']}' copiada!", icon="✅")

                                    with col_chk:
                                        enviado_check = st.checkbox(
                                            "Marcar como enviado",
                                            value=is_enviado,
                                            key=f"chk_env_{msg['id']}"
                                        )
                                        if enviado_check != is_enviado:
                                            st.session_state.enviados[msg_key] = enviado_check
                                            st.rerun()

                                    with st.expander("Vincular grupo no WhatsApp", expanded=False):
                                        st.caption("Cadastre o nome exato do grupo no WhatsApp deste cliente:")
                                        col_v_in, col_v_bt = st.columns([3, 1])
                                        with col_v_in:
                                            novo_nome_grp = st.text_input(
                                                "Nome do grupo no WhatsApp:",
                                                key=f"input_new_grp_{msg['id']}",
                                                placeholder=f"Ex: {msg['nome_conta']} & Brobot",
                                                label_visibility="collapsed"
                                            )
                                        with col_v_bt:
                                            if st.button("Salvar Grupo", key=f"btn_save_new_{msg['id']}", use_container_width=True):
                                                if novo_nome_grp.strip():
                                                    ok_s, res_s = save_client_contact(msg["nome_conta"], novo_nome_grp.strip())
                                                    if ok_s:
                                                        st.toast(res_s, icon="✅")
                                                        st.rerun()
                                                    else:
                                                        st.error(res_s)
                                                else:
                                                    st.error("Digite o nome do grupo.")


    else:
        st.info("Faça o upload de uma planilha Excel (.xlsx, .xls) acima para iniciar a conferência e geração de mensagens.")

# Aba de Gerenciamento de Grupos do WhatsApp
with tab_grupos:
    st.markdown(
        f'<div class="section-heading"><div class="sh-icon">{_ICON["phone"]}</div>Gerenciamento de Grupos do WhatsApp</div>',
        unsafe_allow_html=True
    )
    st.caption(
        "Mapeamento dos grupos de WhatsApp por conta/cliente. "
        "Os grupos cadastrados aqui são usados para abrir o WhatsApp Desktop e colar a mensagem automaticamente."
    )

    db_atual = get_db_path()
    all_contacts = get_all_contacts()

    col_g_info1, col_g_info2 = st.columns([3, 1.5])
    with col_g_info1:
        st.info(
            f"**Banco local:** `{db_atual}`\n\n"
            "Todos os grupos cadastrados ficam salvos neste projeto. "
            "Qualquer alteração aqui não afeta o Central de Erros."
        )
    with col_g_info2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-icon">{_ICON["phone"]}</div>
                <div class="metric-value">{len(all_contacts)}</div>
                <div class="metric-label">Grupos Cadastrados</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # -------------------------------------------------------------------------
    # Painel de Sincronização com o Central de Erros
    # -------------------------------------------------------------------------
    st.markdown("---")
    with st.expander("Sincronizar grupos do Central de Erros", expanded=False):
        st.caption(
            "Importa os grupos de WhatsApp mapeados no **Central de Erros** para este banco local. "
            "Útil quando você cadastrou novos grupos lá e quer refletir aqui sem precisar redigitar."
        )

        _shared_db = r"c:\Gustavo\Central de Erros\data\history.db"
        _shared_exists = os.path.exists(_shared_db)

        col_sync_left, col_sync_right = st.columns([2.5, 1.5])
        with col_sync_left:
            if _shared_exists:
                st.success(f"Central de Erros localizado: `{_shared_db}`")
            else:
                st.error(
                    f"Banco do Central de Erros não encontrado em:\n`{_shared_db}`\n\n"
                    "Verifique se o projeto existe neste caminho."
                )

        with col_sync_right:
            overwrite_mode = st.toggle(
                "Substituir grupos existentes",
                value=False,
                key="toggle_overwrite_sync",
                help=(
                    "**Desligado (padrão):** só importa clientes novos. "
                    "Grupos já cadastrados aqui ficam intactos.\n\n"
                    "**Ligado:** substitui tudo — inclusive grupos que você editou localmente."
                ),
            )

        col_btn_sync, col_btn_info = st.columns([1, 3])
        with col_btn_sync:
            btn_sync = st.button(
                "Sincronizar Agora",
                key="btn_sync_erros",
                type="primary",
                use_container_width=True,
                disabled=not _shared_exists,
            )
        with col_btn_info:
            if overwrite_mode:
                st.warning("Modo substituição ativo — grupos editados aqui serão sobrescritos.")
            else:
                st.info("Modo seguro — apenas grupos **novos** serão importados.")

        if btn_sync:
            with st.spinner("Sincronizando grupos do Central de Erros..."):
                ok_sync, msg_sync, novos_sync, exist_sync = sync_from_central_de_erros(
                    shared_db_path=_shared_db,
                    overwrite_local=overwrite_mode,
                )
            if ok_sync:
                st.success(msg_sync)
                st.rerun()
            else:
                st.error(msg_sync)

    # Se uma planilha estiver carregada e gerando mensagens, lista as pendentes de mapeamento

    if "mensagens" in locals() and mensagens:
        contas_sem_grupo = [m["nome_conta"] for m in mensagens if get_client_contact(m["nome_conta"]) is None]
        if contas_sem_grupo:
            st.markdown("---")
            with st.expander(f"{len(contas_sem_grupo)} Contas Sem Grupo Vinculado (clique para vincular)", expanded=True):
                st.caption("Digite o nome exato do grupo no WhatsApp para cada conta abaixo e clique em Salvar:")
                for c_sem in contas_sem_grupo:
                    col_cs1, col_cs2, col_cs3 = st.columns([2.5, 3, 1])
                    with col_cs1:
                        st.markdown(f"**{c_sem}**")
                    with col_cs2:
                        val_input = st.text_input(
                            f"Grupo de {c_sem}",
                            key=f"tab_g_input_{c_sem}",
                            placeholder=f"Ex: {c_sem} & Brobot",
                            label_visibility="collapsed"
                        )
                    with col_cs3:
                        if st.button("Salvar", key=f"tab_btn_save_{c_sem}", use_container_width=True):
                            if val_input.strip():
                                ok_sc, msg_sc = save_client_contact(c_sem, val_input.strip())
                                if ok_sc:
                                    st.toast(msg_sc, icon="✅")
                                    st.rerun()
                                else:
                                    st.error(msg_sc)
                            else:
                                st.error("Informe o nome do grupo.")
        else:
            st.success("Todas as contas da planilha atual possuem grupos vinculados!")

    st.markdown("---")
    # Cadastrar ou Editar Manualmente
    col_cad1, col_cad2 = st.columns(2)
    with col_cad1:
        st.markdown("##### Cadastrar / Atualizar Grupo")
        nome_cliente_form = st.text_input("Nome da Conta / Cliente (exatamente como na planilha):", key="form_cad_cli")
        nome_grupo_form = st.text_input("Nome do Grupo no WhatsApp:", key="form_cad_grp", placeholder="Ex: Nome da Empresa & Brobot")

        if st.button("Salvar / Atualizar Grupo", key="btn_form_salvar_grp", type="primary"):
            if not nome_cliente_form.strip():
                st.error("Informe o nome da conta.")
            elif not nome_grupo_form.strip():
                st.error("Informe o nome do grupo.")
            else:
                ok_f, msg_f = save_client_contact(nome_cliente_form.strip(), nome_grupo_form.strip())
                if ok_f:
                    st.success(msg_f)
                    st.rerun()
                else:
                    st.error(msg_f)

    with col_cad2:
        st.markdown("##### Remover Vínculo de Grupo")
        if all_contacts:
            cliente_para_remover = st.selectbox(
                "Selecione o cliente para desvincular:",
                options=list(all_contacts.keys()),
                key="sel_del_cli"
            )
            if st.button("Excluir Vínculo", key="btn_del_grp"):
                ok_d, msg_d = delete_client_contact(cliente_para_remover)
                if ok_d:
                    st.success(msg_d)
                    st.rerun()
                else:
                    st.error(msg_d)
        else:
            st.caption("Nenhum grupo cadastrado ainda.")

    st.markdown("---")
    st.markdown("##### Todos os Grupos Mapeados")
    filtro_grupos = st.text_input("Filtrar por cliente ou nome do grupo:", key="filtro_tabela_grupos")

    contatos_filtrados = {
        cli: dados for cli, dados in all_contacts.items()
        if (not filtro_grupos) or (filtro_grupos.lower() in cli.lower() or filtro_grupos.lower() in dados["contact_value"].lower())
    }

    if contatos_filtrados:
        df_contatos = pd.DataFrame([
            {
                "Conta / Cliente": cli,
                "Grupo no WhatsApp": dados["contact_value"],
                "Tipo": dados["contact_type"],
                "Última Atualização": dados["updated_at"]
            }
            for cli, dados in contatos_filtrados.items()
        ])
        st.dataframe(df_contatos, use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhum grupo encontrado com o termo pesquisado.")



