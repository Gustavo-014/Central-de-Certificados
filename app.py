import io
import json
from typing import Any, Dict, List

import pandas as pd
import pyperclip
import streamlit as st

from core.excel_reader import get_sheet_names, read_excel_smart
from core.message_builder import build_all_messages, format_combined_messages
from core.processor import process_dataframe
from core.template_manager import load_templates, save_templates
from core.validator import validate_columns

# Configuração da Página
st.set_page_config(
    page_title="Central de Certificados - Cobrança",
    page_icon="📜",
    layout="wide"
)

# Estilização CSS Moderna com Glassmorphism
st.markdown(
    """
    <style>
    /* Fundo Noturno Elegante */
    .stApp {
        background: radial-gradient(circle at 50% -10%, #1e1b4b 0%, #0f172a 55%, #070a12 100%) !important;
        background-attachment: fixed !important;
    }

    /* Cabeçalho de Alto Impacto */
    .main-title {
        font-size: 2.3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
    }
    .sub-title {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }

    /* Cards de Métricas em Glassmorphism */
    .metric-card {
        background: rgba(21, 28, 44, 0.75);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(129, 140, 248, 0.25);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        border-radius: 12px;
        padding: 14px 18px;
        text-align: center;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: rgba(168, 85, 247, 0.5);
        transform: translateY(-2px);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #38bdf8;
    }
    .metric-value-ok {
        font-size: 1.8rem;
        font-weight: 800;
        color: #34d399;
    }
    .metric-value-warn {
        font-size: 1.8rem;
        font-weight: 800;
        color: #fbbf24;
    }
    .metric-value-alert {
        font-size: 1.8rem;
        font-weight: 800;
        color: #f87171;
    }
    .metric-label {
        font-size: 0.82rem;
        color: #cbd5e1;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        font-weight: 600;
    }

    /* Caixa de Mensagem */
    div[data-baseweb="textarea"] textarea {
        background-color: rgba(15, 23, 42, 0.95) !important;
        color: #f1f5f9 !important;
        border: 1px solid rgba(129, 140, 248, 0.3) !important;
        border-radius: 10px !important;
        font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace !important;
        font-size: 0.90rem !important;
        line-height: 1.5 !important;
    }

    /* Expander e Cards */
    .stApp div[data-testid="stExpander"] {
        background: rgba(17, 24, 39, 0.65) !important;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(99, 102, 241, 0.25) !important;
        border-radius: 12px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }

    /* Badges de Status */
    .status-badge {
        display: inline-block;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 6px;
        margin-right: 6px;
    }
    .badge-expired {
        background-color: rgba(239, 68, 68, 0.2);
        color: #fca5a5;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .badge-warning {
        background-color: rgba(245, 158, 11, 0.2);
        color: #fcd34d;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
    .badge-info {
        background-color: rgba(59, 130, 246, 0.2);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.4);
    }
    .badge-neutral {
        background-color: rgba(107, 114, 128, 0.2);
        color: #d1d5db;
        border: 1px solid rgba(107, 114, 128, 0.4);
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Inicializa Session State para templates e controle de envios
if "templates" not in st.session_state:
    st.session_state.templates = load_templates()
if "enviados" not in st.session_state:
    st.session_state.enviados = {}

# Header da Aplicação
st.markdown('<div class="main-title">Central de Certificados</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Automação de conferência e cobrança de certificados digitais por conta e data de vencimento.</div>',
    unsafe_allow_html=True
)

# Abas Principais
tab_mensagens, tab_templates, tab_ajuda = st.tabs([
    "💬 Mensagens de Cobrança",
    "⚙️ Gerenciador de Templates",
    "ℹ️ Informações e Instruções"
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
                    "📑 Selecione a Aba da Planilha:",
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
                st.error(f"❌ Erro ao ler a planilha: {e}")
                df_mapped = None
                missing_cols = ["Erro na leitura"]

            if df_mapped is not None:
                if missing_cols:
                    st.error(
                        f"❌ **Colunas Obrigatórias Ausentes na aba '{selected_sheet}'!**\n\n"
                        f"As seguintes colunas não foram identificadas:\n\n"
                        + "\n".join([f"- `{col}`" for col in missing_cols])
                        + "\n\n**Colunas encontradas nesta aba:**\n"
                        + ", ".join([f"`{c}`" for c in df_mapped.columns if not str(c).startswith("Unnamed")])
                    )
                    if len(available_sheets) > 1:
                        st.info("💡 Como o seu arquivo possui várias abas, você pode selecionar outra aba no campo acima.")
                else:
                    if len(available_sheets) > 1 or h_row_used > 0:
                        st.caption(f"✅ Aba ativa: **{sheet_used}** (Cabeçalho detectado na linha {h_row_used + 1})")

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
                    m1, m2, m3, m4, m5 = st.columns(5)

                    with m1:
                        st.markdown(
                            f"""
                            <div class="metric-card">
                                <div class="metric-value">{result.total_linhas}</div>
                                <div class="metric-label">Total de Linhas</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with m2:
                        st.markdown(
                            f"""
                            <div class="metric-card">
                                <div class="metric-value-ok">{result.total_ok}</div>
                                <div class="metric-label">Certificado OK (Ignorados)</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with m3:
                        st.markdown(
                            f"""
                            <div class="metric-card">
                                <div class="metric-value-warn">{result.total_acao}</div>
                                <div class="metric-label">Precisam de Ação</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with m4:
                        st.markdown(
                            f"""
                            <div class="metric-card">
                                <div class="metric-value">{result.total_mensagens}</div>
                                <div class="metric-label">Mensagens Geradas</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with m5:
                        metric_enviados_class = "metric-value-ok" if (total_enviados == len(mensagens) and len(mensagens) > 0) else "metric-value"
                        st.markdown(
                            f"""
                            <div class="metric-card">
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
                            "⚠️ **Atenção: Status Não Configurados Encontrados na Planilha!**\n\n"
                            "Os seguintes valores de status não possuem template configurado:\n\n"
                            + "\n".join([f"- `{st_desc}`" for st_desc in result.status_desconhecidos])
                            + "\n\n*Você pode configurar novos templates para esses status na aba 'Gerenciador de Templates'.*"
                        )

                    # Alertas de Registros Incompletos / Problemáticos
                    if result.registros_problematicos:
                        with st.expander(f"⚠️ {len(result.registros_problematicos)} Registros com Dados Incompletos / Inválidos (Clique para ver)", expanded=False):
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

                    st.markdown("### 📋 Mensagens Prontas para Envio")

                    if not mensagens:
                        st.info("Nenhuma mensagem precisou ser gerada. Todos os registros estão como 'CERTIFICADO OK' ou foram desconsiderados.")
                    else:
                        # Barra de Ferramentas: Filtros e Ações
                        col_busca, col_filtro_status, col_filtro_envio, col_btn_todas = st.columns([2.5, 2, 1.8, 2.2])

                        with col_busca:
                            termo_busca = st.text_input("🔍 Buscar por Nome da Conta ou Empresa:", placeholder="Digite para filtrar...")

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

                        with col_btn_todas:
                            st.write("")  # Espaçamento vertical
                            if total_enviados > 0:
                                col_b1, col_b2 = st.columns([1.2, 1])
                                with col_b1:
                                    if st.button("📑 Copiar Todas", use_container_width=True, help="Copia todas as mensagens atualmente filtradas"):
                                        texto_combinado = format_combined_messages(mensagens_filtradas)
                                        pyperclip.copy(texto_combinado)
                                        st.toast(f"✅ {len(mensagens_filtradas)} mensagens copiadas!", icon="📋")
                                tapestry_reset = col_b2 if total_enviados > 0 else None
                                with col_b2:
                                    if st.button("🔄 Resetar", use_container_width=True, help="Desmarca todas as mensagens como enviadas"):
                                        for m in mensagens:
                                            mk = m["nome_conta"]
                                            wk = f"chk_env_{m['id']}"
                                            st.session_state.enviados[mk] = False
                                            if wk in st.session_state:
                                                st.session_state[wk] = False
                                        st.rerun()
                            else:
                                if st.button("📑 Copiar Todas as Mensagens", use_container_width=True, help="Copia todas as mensagens atualmente filtradas"):
                                    texto_combinado = format_combined_messages(mensagens_filtradas)
                                    pyperclip.copy(texto_combinado)
                                    st.toast(f"✅ {len(mensagens_filtradas)} mensagens copiadas!", icon="📋")

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
                            tag_multi = " [MULTI-STATUS]" if msg.get("is_multi_status") else ""
                            if is_enviado:
                                titulo_card = f"✅ {msg['nome_conta']}{tag_multi}  |  📅 Vencimento: {venc_card}  |  🔢 {msg['quantidade_cnpjs']} CNPJ(s)  —  [ENVIADO]"
                            else:
                                titulo_card = f"🏢 {msg['nome_conta']}{tag_multi}  |  📅 Vencimento: {venc_card}  |  🔢 {msg['quantidade_cnpjs']} CNPJ(s)"

                            with st.expander(titulo_card, expanded=not is_enviado):
                                badge_enviado_html = (
                                    '<span class="status-badge" style="background-color: rgba(16, 185, 129, 0.25); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.45);">✅ ENVIADO</span>'
                                    if is_enviado
                                    else '<span class="status-badge" style="background-color: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.35);">⏳ PENDENTE</span>'
                                )
                                st.markdown(
                                    f"""
                                    <div style="margin-bottom: 8px;">
                                        {badge_enviado_html}
                                        {badges_status_html}
                                        <span class="status-badge badge-neutral">Vencimento: {venc_card}</span>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )

                                col_msg, col_detalhes = st.columns([3, 2])

                                with col_msg:
                                    st.text_area(
                                        label="Texto da Mensagem:",
                                        value=msg["mensagem"],
                                        height=240,
                                        key=f"txt_msg_{msg['id']}"
                                    )

                                    col_cp, col_chk = st.columns([1.2, 1.8])
                                    with col_cp:
                                        if st.button("📋 Copiar Mensagem", key=f"btn_copy_{msg['id']}", use_container_width=True):
                                            pyperclip.copy(msg["mensagem"])
                                            st.toast(f"Mensagem de '{msg['nome_conta']}' copiada com sucesso!", icon="📋")

                                    with col_chk:
                                        enviado_check = st.checkbox(
                                            "✅ Enviado ao cliente",
                                            value=is_enviado,
                                            key=f"chk_env_{msg['id']}"
                                        )
                                        if enviado_check != is_enviado:
                                            st.session_state.enviados[msg_key] = enviado_check
                                            st.rerun()

                                with col_detalhes:
                                    st.markdown("**Empresas / CNPJs Agrupados:**")
                                    for it in msg["itens"]:
                                        st.markdown(f"- **{it['empresa']}**\n  `CNPJ: {it['cnpj']}` | Vencimento: `{it['data_expiracao']}` (Linha {it['linha']})")

    else:
        st.info("👈 Faça o upload de uma planilha Excel (.xlsx, .xls) acima para iniciar a conferência e geração de mensagens.")

# Aba de Gerenciador de Templates
with tab_templates:
    st.markdown("### ⚙️ Gerenciamento de Templates por Status")
    st.caption(
        "Edite os textos das mensagens ou cadastre novos templates associados ao 'status do fluxo'. "
        "As alterações são salvas e aplicadas imediatamente."
    )

    templates_atuais = st.session_state.templates

    col_t_sel, col_t_actions = st.columns([2, 1])

    status_options = list(templates_atuais.keys())
    status_escolhido = col_t_sel.selectbox("Selecione o Status para visualizar/editar:", status_options)

    if status_escolhido:
        t_data = templates_atuais[status_escolhido]
        t_desc = t_data.get("descricao", "") if isinstance(t_data, dict) else ""
        t_corpo = t_data.get("template", "") if isinstance(t_data, dict) else str(t_data)

        nova_desc = st.text_input("Descrição amigável do status:", value=t_desc, key="edit_desc")
        novo_corpo = st.text_area(
            "Texto do Template (Placeholders disponíveis: {clientes}, {cnpjs}, {data_expiracao}, {nome_conta}, {secoes_status}):",
            value=t_corpo,
            height=280,
            key="edit_corpo"
        )

        col_salvar, col_delete = st.columns([1, 4])
        with col_salvar:
            if st.button("💾 Salvar Alterações", key="btn_salvar_template", use_container_width=True):
                st.session_state.templates[status_escolhido] = {
                    "descricao": nova_desc,
                    "template": novo_corpo
                }
                save_templates(st.session_state.templates)
                st.success(f"Template '{status_escolhido}' atualizado com sucesso!")
                st.rerun()

    st.markdown("---")
    with st.expander("➕ Cadastrar Novo Status / Template", expanded=False):
        novo_status_nome = st.text_input("Nome Exato do Status do Fluxo (conforme vem na planilha):", key="novo_st_nome")
        novo_status_desc = st.text_input("Descrição amigável:", key="novo_st_desc")
        novo_status_template = st.text_area(
            "Texto do Template:",
            value="Olá! Tudo bem?\n\nVerificamos que o Certificado Digital dos CNPJs expiram em breve.\n\n{clientes}\n{cnpjs}\n{data_expiracao}\n\nA atualização das credenciais é fundamental para o sucesso das consultas.\n\nPara restabelecer as consultas, orientamos que as novas credenciais sejam atualizadas e incluídas na nossa plataforma o quanto antes.\n\nSegue link de auxílio de como inserir o Certificado na plataforma:\nhttps://drive.google.com/file/d/12lZ05WHZ_eLwVy83iAw1VvQ9rumXSnnV/view?usp=sharing\n\nQualquer dúvida, é só nos chamar.\nFicamos à disposição!",
            height=200,
            key="novo_st_template"
        )

        if st.button("Cadastrar Novo Template", key="btn_cadastrar_novo"):
            if not novo_status_nome.strip():
                st.error("Informe o nome do status.")
            else:
                st.session_state.templates[novo_status_nome.strip()] = {
                    "descricao": novo_status_desc.strip(),
                    "template": novo_status_template.strip()
                }
                save_templates(st.session_state.templates)
                st.success(f"Novo status '{novo_status_nome}' cadastrado com sucesso!")
                st.rerun()

# Aba de Ajuda e Instruções
with tab_ajuda:
    st.markdown("### ℹ️ Regras de Funcionamento e Formato da Planilha")
    st.markdown(
        """
        **1. Colunas Obrigatórias da Planilha:**
        A planilha importada deve conter obrigatoriamente estas 5 colunas:
        - `Nome da Conta`
        - `Empresa`
        - `CNPJ`
        - `Certificado Expira em`
        - `status do fluxo`

        *Todas as demais colunas existentes na planilha são ignoradas.*

        ---

        **2. Regra de Negócio do Status:**
        - Registros com status exatamente igual a `CERTIFICADO OK` são **desconsiderados** e não geram mensagem.
        - Registros com outros status geram mensagens baseadas nos templates cadastrados.
        - Se o mesmo cliente tiver status diferentes, é gerada uma **única mensagem unificada** utilizando o template `MULTI-STATUS`.
        - Se surgir algum status na planilha que não esteja cadastrado, ele será apontado na tela para que você possa cadastrar o template correspondente.

        ---

        **3. Agrupamento:**
        - O agrupamento de registros é feito por **Nome da Conta**, mantendo todos os CNPJs e status do mesmo cliente na mesma mensagem.
        - **Status Único:** Se todos os CNPJs da conta compartilham o mesmo status, o template específico daquele status é utilizado.
        - **Multi-Status:** Se a mesma conta tiver certificados com status diferentes (ex: um vencendo em 5 dias e outro já expirado), os CNPJs são organizados em seções separadas por status dentro da mesma mensagem usando o template `MULTI-STATUS`.
        - Caso a conta tenha certificados vencendo em **datas diferentes**, o vencimento de cada um é detalhado abaixo do CNPJ:
          ```
          Cliente: Nome da Empresa
          CNPJ: 00.000.000/0001-00
          Vencimento: DD/MM/AAAA
          ```

        ---

        **4. Placeholders dos Templates:**
        - `{secoes_status}`: Usado no template MULTI-STATUS para inserir os blocos organizados por seção de status.
        - `{clientes}`: Lista das empresas/clientes, um por linha.
        - `{cnpjs}`: Lista dos CNPJs formatados, um por linha.
        - `{data_expiracao}`: Lista das datas de vencimento (`DD/MM/AAAA`), uma por linha correspondente a cada cliente/CNPJ.
        - `{nome_conta}`: Nome da conta principal do cliente.
        - `{clientes_cnpjs}`: Lista dos pares no formato legado (Cliente / CNPJ).
        """
    )

