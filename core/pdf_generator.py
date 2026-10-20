import os
import re
from datetime import datetime
from typing import Any, Dict, List

from fpdf import FPDF
from fpdf.enums import XPos, YPos


def sanitize_text(text: Any) -> str:
    """Remove caracteres especiais, emojis e símbolos incompatíveis com a fonte."""
    if text is None:
        return ""
    s = str(text)
    # Remove emojis e caracteres fora do plano BMP
    s = re.sub(r"[\U00010000-\U0010ffff]", "", s)
    # Remove dingbats e símbolos gráficos comuns
    s = re.sub(r"[\u25A0-\u27BF]", "", s)
    # Remove variações invisíveis de espaçamento
    s = s.replace("\xa0", " ")
    return s.strip()


class CertificatePDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.font_family_name = "Helvetica"
        self._setup_fonts()

    def _setup_fonts(self):
        """Configura fontes com suporte a caracteres acentuados se disponíveis no Windows."""
        font_dir = r"C:\Windows\Fonts"
        fonts = {
            "": os.path.join(font_dir, "arial.ttf"),
            "B": os.path.join(font_dir, "arialbd.ttf"),
            "I": os.path.join(font_dir, "ariali.ttf"),
        }
        if all(os.path.exists(p) for p in fonts.values()):
            try:
                for style, path in fonts.items():
                    self.add_font("Arial", style, path)
                self.font_family_name = "Arial"
            except Exception:
                self.font_family_name = "Helvetica"
        else:
            self.font_family_name = "Helvetica"

    def header(self):
        # Linha de destaque no topo
        self.set_fill_color(37, 99, 235)  # Azul Royal
        self.rect(0, 0, 210, 4, "F")

        self.set_y(8)
        self.set_font(self.font_family_name, "B", 14)
        self.set_text_color(30, 41, 59)
        self.cell(0, 7, "CENTRAL DE CERTIFICADOS DIGITAIS", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

        self.set_font(self.font_family_name, "", 9)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, "Relatorio de Controle e Acompanhamento de Envios", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

        self.set_draw_color(226, 232, 240)
        self.line(10, 22, 200, 22)
        self.ln(6)

    def footer(self):
        self.set_y(-12)
        self.set_font(self.font_family_name, "I", 8)
        self.set_text_color(148, 163, 184)
        self.cell(
            0,
            5,
            f"Pagina {self.page_no()}/{{nb}}  |  Central de Certificados  |  Documento gerado automaticamente",
            align="C",
        )


def generate_pdf_report(
    mensagens: List[Dict[str, Any]],
    enviados: Dict[str, bool],
    result: Any,
    nome_arquivo: str = "",
    nome_aba: str = "",
) -> bytes:
    """
    Gera um relatório completo em PDF diferenciando as mensagens enviadas e pendentes.
    Retorna os bytes do PDF gerado.
    """
    pdf = CertificatePDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    fn = pdf.font_family_name
    agora_str = datetime.now().strftime("%d/%m/%Y as %H:%M:%S")

    # Separar enviadas e pendentes
    lista_enviados = []
    lista_pendentes = []

    for msg in mensagens:
        conta = msg["nome_conta"]
        if enviados.get(conta, False):
            lista_enviados.append(msg)
        else:
            lista_pendentes.append(msg)

    total_msgs = len(mensagens)
    total_env = len(lista_enviados)
    total_pen = len(lista_pendentes)
    pct_env = int((total_env / total_msgs * 100)) if total_msgs > 0 else 0
    pct_pen = int((total_pen / total_msgs * 100)) if total_msgs > 0 else 0

    # Metadados do Relatório
    pdf.set_font(fn, "", 8)
    pdf.set_text_color(71, 85, 105)

    info_text = f"Emissao: {agora_str}"
    if nome_arquivo:
        info_text += f"   |   Arquivo: {sanitize_text(nome_arquivo)}"
    if nome_aba:
        info_text += f"   |   Aba: {sanitize_text(nome_aba)}"

    pdf.cell(0, 5, info_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # =========================================================================
    # CARDS DE INDICADORES (KPIs)
    # =========================================================================
    card_w = 46
    card_h = 18
    gap = 2
    y_start = pdf.get_y()

    # 1. Total Mensagens
    pdf.set_xy(10, y_start)
    pdf.set_fill_color(241, 245, 249)
    pdf.set_draw_color(203, 213, 225)
    pdf.rect(10, y_start, card_w, card_h, "FD")
    pdf.set_xy(10, y_start + 2)
    pdf.set_font(fn, "B", 13)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(card_w, 6, str(total_msgs), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(10)
    pdf.set_font(fn, "", 7)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(card_w, 4, "TOTAL DE CLIENTES", align="C")

    # 2. Mensagens Enviadas
    x2 = 10 + card_w + gap
    pdf.set_xy(x2, y_start)
    pdf.set_fill_color(240, 253, 244)  # Verde Claro
    pdf.set_draw_color(187, 247, 208)
    pdf.rect(x2, y_start, card_w, card_h, "FD")
    pdf.set_xy(x2, y_start + 2)
    pdf.set_font(fn, "B", 13)
    pdf.set_text_color(22, 101, 52)  # Verde Escuro
    pdf.cell(card_w, 6, f"{total_env} ({pct_env}%)", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(x2)
    pdf.set_font(fn, "B", 7)
    pdf.set_text_color(21, 128, 61)
    pdf.cell(card_w, 4, "ENVIADOS / CONCLUIDOS", align="C")

    # 3. Mensagens Pendentes
    x3 = x2 + card_w + gap
    pdf.set_xy(x3, y_start)
    pdf.set_fill_color(254, 243, 199)  # Ambar Claro
    pdf.set_draw_color(253, 230, 138)
    pdf.rect(x3, y_start, card_w, card_h, "FD")
    pdf.set_xy(x3, y_start + 2)
    pdf.set_font(fn, "B", 13)
    pdf.set_text_color(180, 83, 9)  # Ambar Escuro
    pdf.cell(card_w, 6, f"{total_pen} ({pct_pen}%)", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(x3)
    pdf.set_font(fn, "B", 7)
    pdf.set_text_color(180, 83, 9)
    pdf.cell(card_w, 4, "PENDENTES / NAO ENVIADOS", align="C")

    # 4. Certificados OK (Ignorados)
    x4 = x3 + card_w + gap
    total_ok = getattr(result, "total_ok", 0)
    pdf.set_xy(x4, y_start)
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.rect(x4, y_start, card_w, card_h, "FD")
    pdf.set_xy(x4, y_start + 2)
    pdf.set_font(fn, "B", 13)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(card_w, 6, str(total_ok), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(x4)
    pdf.set_font(fn, "", 7)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(card_w, 4, "CERTIFICADOS OK (IGNORADOS)", align="C")

    pdf.set_y(y_start + card_h + 6)

    # =========================================================================
    # TABELA CONSOLIDADA RESUMIDA (TODOS OS CLIENTES)
    # =========================================================================
    pdf.set_font(fn, "B", 10)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 6, "1. RESUMO GERAL DE ENVIOS POR CONTA", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)

    # Cabecalho da Tabela
    col_w = [26, 75, 45, 24, 20]  # Total: 190 mm
    headers = ["STATUS ENVIO", "CONTA / CLIENTE", "STATUS DO CERTIFICADO", "VENCIMENTO", "QTD CNPJ"]

    def desenhar_cabecalho_resumo():
        pdf.set_fill_color(226, 232, 240)
        pdf.set_draw_color(203, 213, 225)
        pdf.set_font(fn, "B", 8)
        pdf.set_text_color(30, 41, 59)
        for i, h in enumerate(headers):
            align = "C" if i in [0, 3, 4] else "L"
            pdf.cell(col_w[i], 6, h, border=1, align=align, fill=True)
        pdf.ln()

    desenhar_cabecalho_resumo()

    for idx, msg in enumerate(mensagens, start=1):
        if pdf.get_y() > 270:
            pdf.add_page()
            desenhar_cabecalho_resumo()

        conta = msg["nome_conta"]
        is_env = enviados.get(conta, False)
        venc = "Diversos" if msg.get("tem_datas_diferentes") else msg["data_expiracao"]
        status_desc = " / ".join(msg.get("statuses", [msg["status"]]))
        if len(status_desc) > 30:
            status_desc = status_desc[:28] + "..."

        nome_exib = sanitize_text(conta)
        if len(nome_exib) > 42:
            nome_exib = nome_exib[:40] + "..."

        row_fill = (idx % 2 == 0)

        # Coluna Status Envio (Pill/Badge colorida)
        if is_env:
            pdf.set_fill_color(220, 252, 231)
            pdf.set_text_color(22, 101, 52)
            pdf.set_font(fn, "B", 7)
            status_env_text = "ENVIADO"
        else:
            pdf.set_fill_color(254, 243, 199)
            pdf.set_text_color(180, 83, 9)
            pdf.set_font(fn, "B", 7)
            status_env_text = "PENDENTE"

        pdf.set_draw_color(226, 232, 240)
        pdf.cell(col_w[0], 5, status_env_text, border=1, align="C", fill=True)

        # Demais Colunas
        if row_fill:
            pdf.set_fill_color(248, 250, 252)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.set_text_color(30, 41, 59)
        pdf.set_font(fn, "", 8)
        pdf.cell(col_w[1], 5, f"  {nome_exib}", border=1, align="L", fill=True)

        pdf.set_font(fn, "", 7)
        pdf.cell(col_w[2], 5, f"  {sanitize_text(status_desc)}", border=1, align="L", fill=True)

        pdf.cell(col_w[3], 5, sanitize_text(venc), border=1, align="C", fill=True)
        pdf.cell(col_w[4], 5, str(msg["quantidade_cnpjs"]), border=1, align="C", fill=True)
        pdf.ln()

    pdf.ln(5)

    # =========================================================================
    # DETALHAMENTO COMPLETO POR CONTA (SEPARADO POR ENVIADAS E PENDENTES)
    # =========================================================================
    def render_secao_detalhes(titulo: str, lista_msgs: List[Dict[str, Any]], is_env_flag: bool):
        if pdf.get_y() > 250:
            pdf.add_page()

        pdf.set_font(fn, "B", 10)
        if is_env_flag:
            pdf.set_text_color(22, 101, 52)
            bg_bar = (220, 252, 231)
            bdr_bar = (187, 247, 208)
        else:
            pdf.set_text_color(180, 83, 9)
            bg_bar = (254, 243, 199)
            bdr_bar = (253, 230, 138)

        # Barra de Titulo da Secao
        pdf.set_fill_color(*bg_bar)
        pdf.set_draw_color(*bdr_bar)
        pdf.cell(190, 7, f"  {titulo}", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

        if not lista_msgs:
            pdf.set_font(fn, "I", 8)
            pdf.set_text_color(100, 116, 139)
            msg_vazia = "Nenhum cliente neste status." if is_env_flag else "Parabens! Nenhum envio pendente."
            pdf.cell(0, 6, msg_vazia, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(3)
            return

        for m in lista_msgs:
            if pdf.get_y() > 250:
                pdf.add_page()

            venc = "Datas diferentes" if m.get("tem_datas_diferentes") else m["data_expiracao"]
            st_text = " / ".join(m.get("statuses", [m["status"]]))

            # Cabecalho do Card da Conta
            pdf.set_draw_color(203, 213, 225)
            pdf.set_fill_color(241, 245, 249)
            pdf.set_font(fn, "B", 8)
            pdf.set_text_color(15, 23, 42)

            tag_envio = "[ENVIADO]" if is_env_flag else "[PENDENTE]"
            header_str = f"  {tag_envio}  {sanitize_text(m['nome_conta'])}   |   Vencimento: {sanitize_text(venc)}   |   CNPJ(s): {m['quantidade_cnpjs']}"
            pdf.cell(190, 6, header_str, border="LTR", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            # Sub-cabecalho de status
            pdf.set_font(fn, "", 7)
            pdf.set_text_color(71, 85, 105)
            pdf.cell(190, 4, f"   Status do Fluxo: {sanitize_text(st_text)}", border="LR", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            # Tabela de CNPJs / Empresas agrupadas
            col_det_w = [85, 45, 35, 25]
            det_headers = ["Empresa / Razao Social", "CNPJ", "Vencimento", "Linha Planilha"]

            pdf.set_fill_color(226, 232, 240)
            pdf.set_font(fn, "B", 7)
            pdf.set_text_color(51, 65, 85)
            for i, dh in enumerate(det_headers):
                align = "C" if i in [1, 2, 3] else "L"
                pdf.cell(col_det_w[i], 4, f" {dh}" if align == "L" else dh, border=1, align=align, fill=True)
            pdf.ln()

            pdf.set_font(fn, "", 7)
            pdf.set_text_color(30, 41, 59)
            for item in m["itens"]:
                pdf.set_fill_color(255, 255, 255)
                emp_txt = sanitize_text(item["empresa"])
                if len(emp_txt) > 50:
                    emp_txt = emp_txt[:48] + "..."
                pdf.cell(col_det_w[0], 4, f"  {emp_txt}", border=1, align="L", fill=True)
                pdf.cell(col_det_w[1], 4, sanitize_text(item["cnpj"]), border=1, align="C", fill=True)
                pdf.cell(col_det_w[2], 4, sanitize_text(item["data_expiracao"]), border=1, align="C", fill=True)
                linha_num = item.get("linha", item.get("linha_excel", ""))
                pdf.cell(col_det_w[3], 4, str(linha_num), border=1, align="C", fill=True)
                pdf.ln()

            pdf.ln(3)

    render_secao_detalhes(
        f"2. CLIENTES ENVIADOS / CONCLUIDOS ({total_env})",
        lista_enviados,
        is_env_flag=True,
    )

    pdf.ln(2)

    render_secao_detalhes(
        f"3. CLIENTES PENDENTES / NAO ENVIADOS ({total_pen})",
        lista_pendentes,
        is_env_flag=False,
    )

    # =========================================================================
    # REGISTROS INCOMPLETOS / PROBLEMATICOS (SE HOUVER)
    # =========================================================================
    problematicos = getattr(result, "registros_problematicos", [])
    if problematicos:
        if pdf.get_y() > 240:
            pdf.add_page()

        pdf.set_font(fn, "B", 10)
        pdf.set_text_color(185, 28, 28)
        pdf.set_fill_color(254, 226, 226)
        pdf.set_draw_color(252, 165, 165)
        pdf.cell(
            190,
            7,
            f"  4. REGISTROS DESCONSIDERADOS DA PLANILHA ({len(problematicos)})",
            border=1,
            fill=True,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(1)

        pdf.set_font(fn, "I", 7)
        pdf.set_text_color(127, 29, 29)
        pdf.cell(
            0,
            4,
            "Estes registros continham dados incompletos ou invalidos e nao geraram mensagens:",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(1)

        prob_cols = [15, 45, 55, 35, 40]
        prob_headers = ["Linha", "Conta", "Empresa", "CNPJ", "Problema"]

        pdf.set_fill_color(241, 245, 249)
        pdf.set_font(fn, "B", 7)
        pdf.set_text_color(30, 41, 59)
        for i, ph in enumerate(prob_headers):
            align = "C" if i in [0, 3] else "L"
            pdf.cell(prob_cols[i], 4, f" {ph}" if align == "L" else ph, border=1, align=align, fill=True)
        pdf.ln()

        pdf.set_font(fn, "", 6)
        for p in problematicos:
            if pdf.get_y() > 275:
                pdf.add_page()
            motivos = ", ".join(p.get("motivos", []))
            pdf.cell(prob_cols[0], 4, str(p.get("linha", "")), border=1, align="C")
            pdf.cell(prob_cols[1], 4, f" {sanitize_text(p.get('nome_conta', ''))[:22]}", border=1)
            pdf.cell(prob_cols[2], 4, f" {sanitize_text(p.get('empresa', ''))[:28]}", border=1)
            pdf.cell(prob_cols[3], 4, sanitize_text(p.get("cnpj", "")), border=1, align="C")
            pdf.cell(prob_cols[4], 4, f" {sanitize_text(motivos)[:22]}", border=1)
            pdf.ln()

    # Retorna os bytes do PDF
    return bytes(pdf.output())
