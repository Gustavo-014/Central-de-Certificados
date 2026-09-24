import re
from typing import Any, Dict, List

from core.processor import CertificateGroup, StatusSubGroup
from core.template_manager import get_template_text, normalize_status


# Mapeamento de emojis por status para cabeçalhos de seção multi-status
STATUS_SECTION_EMOJI = {
    "ENTRAR EM CONTATO, CERTIFICADO EXPIRADO": "📛",
    "ENTRAR EM CONTATO, EXPIRA HOJE!": "🚨",
    "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS": "⚠️",
    "ENTRAR EM CONTATO, EXPIRA EM 15 DIAS": "🔔",
    "CERTIFICADO EXPIRA EM 30 DIAS": "📅",
}


def _get_section_emoji(status_norm: str) -> str:
    """Retorna emoji para o cabeçalho de seção do status."""
    return STATUS_SECTION_EMOJI.get(status_norm, "⚠️")


def format_clientes_cnpjs(group: CertificateGroup) -> str:
    """Formata os pares de Cliente e CNPJ respeitando o layout:
    
    Se houver datas de vencimento diferentes no grupo:
    Cliente: Empresa A
    CNPJ: 00.000.000/0001-00
    Vencimento: 01/10/2026

    Se todos tiverem a mesma data de vencimento:
    Cliente: Empresa A
    CNPJ: 00.000.000/0001-00
    """
    blocos = []
    for item in group.itens:
        if group.tem_datas_diferentes:
            bloco = f"Cliente: {item.empresa}\nCNPJ: {item.cnpj}\nVencimento: {item.data_expiracao}"
        else:
            bloco = f"Cliente: {item.empresa}\nCNPJ: {item.cnpj}"
        blocos.append(bloco)

    return "\n\n".join(blocos)


def _format_sub_group_items(sub_group: StatusSubGroup) -> str:
    """Formata os itens de um sub-grupo (sempre com vencimento)."""
    blocos = []
    for item in sub_group.itens:
        bloco = f"Cliente: {item.empresa}\nCNPJ: {item.cnpj}\nVencimento: {item.data_expiracao}"
        blocos.append(bloco)
    return "\n\n".join(blocos)


def build_status_sections(group: CertificateGroup) -> str:
    """Renderiza as seções de status para mensagens multi-status.
    
    Cada seção contém um cabeçalho com emoji e status, seguido dos
    blocos de Cliente/CNPJ/Vencimento correspondentes.
    """
    sections = []
    for sg in group.sub_groups:
        emoji = _get_section_emoji(sg.status_normalizado)
        header = f"{emoji} {sg.status}:"
        items_text = _format_sub_group_items(sg)
        sections.append(f"{header}\n\n{items_text}")

    return "\n\n".join(sections)


def build_single_message(
    group: CertificateGroup,
    templates: Dict[str, Any]
) -> str:
    """Gera o texto completo da mensagem para um grupo de certificados.
    
    - Para grupos com um único status: usa o template do status correspondente.
    - Para grupos multi-status: usa o template 'MULTI-STATUS' com o placeholder
      {secoes_status} sendo substituído pelas seções renderizadas.
    
    Quando o template contiver um bloco contíguo de linhas com os placeholders
    {clientes}, {cnpjs} e {data_expiracao}, esse bloco é renderizado junto para cada
    registro individual (empresa, CNPJ e data juntos, separados por linha em branco).
    """
    # ── Multi-status: usa template dedicado ──
    if group.is_multi_status:
        template_str = get_template_text("MULTI-STATUS", templates)

        if not template_str:
            # Fallback caso o template MULTI-STATUS não esteja cadastrado
            secoes = build_status_sections(group)
            return (
                f"Olá! Tudo bem?\n\n"
                f"Verificamos pendências nos Certificados Digitais vinculados à conta {group.nome_conta}.\n\n"
                f"{secoes}\n\n"
                f"A atualização das credenciais é fundamental para o sucesso das consultas.\n\n"
                f"Qualquer dúvida, é só nos chamar.\nFicamos à disposição!"
            )

        secoes = build_status_sections(group)
        mensagem = template_str
        mensagem = mensagem.replace("{secoes_status}", secoes)
        mensagem = mensagem.replace("{nome_conta}", group.nome_conta)
        mensagem = mensagem.replace("{conta}", group.nome_conta)
        return mensagem.strip()

    # ── Status único: lógica original ──
    template_str = get_template_text(group.status, templates)

    if not template_str:
        clientes_str = format_clientes_cnpjs(group)
        venc_str = "Datas diferentes" if group.tem_datas_diferentes else group.data_expiracao
        return (
            f"⚠️ [MENSAGEM NÃO GERADA: O status '{group.status}' não possui template cadastrado.]\n\n"
            f"Conta: {group.nome_conta}\n"
            f"Vencimento: {venc_str}\n\n"
            f"{clientes_str}"
        )

    mensagem = template_str

    # 1. Procura bloco contíguo contendo placeholders por item ({clientes}, {cnpjs}, {data_expiracao})
    pattern = re.compile(
        r'((?:^[^\n]*\{(?:clientes?|cnpjs?|datas?_expiracao)\}[^\n]*$\r?\n?){2,3})',
        re.MULTILINE
    )
    match = pattern.search(mensagem)
    if match and group.itens:
        raw_block = match.group(1)
        had_trailing_newline = raw_block.endswith('\n')
        block_lines = raw_block.rstrip('\r\n')

        rendered_blocks = []
        for it in group.itens:
            b = block_lines
            b = re.sub(r'\{clientes?\}', it.empresa, b)
            b = re.sub(r'\{cnpjs?\}', it.cnpj, b)
            b = re.sub(r'\{datas?_expiracao\}', it.data_expiracao, b)
            rendered_blocks.append(b)

        replacement = "\n\n".join(rendered_blocks)
        if had_trailing_newline:
            replacement += "\n"

        mensagem = mensagem[:match.start(1)] + replacement + mensagem[match.end(1):]

    # 2. Substituição para placeholders isolados ou retrocompatíveis
    clientes_text = "\n".join(it.empresa for it in group.itens)
    cnpjs_text = "\n".join(it.cnpj for it in group.itens)
    datas_text = "\n".join(it.data_expiracao for it in group.itens)
    clientes_cnpjs_text = format_clientes_cnpjs(group)

    mensagem = mensagem.replace("{clientes}", clientes_text)
    mensagem = mensagem.replace("{cliente}", clientes_text)
    mensagem = mensagem.replace("{cnpjs}", cnpjs_text)
    mensagem = mensagem.replace("{cnpj}", cnpjs_text)
    mensagem = mensagem.replace("{data_expiracao}", datas_text)
    mensagem = mensagem.replace("{datas_expiracao}", datas_text)
    mensagem = mensagem.replace("{clientes_cnpjs}", clientes_cnpjs_text)
    mensagem = mensagem.replace("{nome_conta}", group.nome_conta)
    mensagem = mensagem.replace("{conta}", group.nome_conta)

    return mensagem.strip()


def build_all_messages(
    groups: List[CertificateGroup],
    templates: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Gera todas as mensagens estruturadas para exibição e cópia na UI."""
    result = []
    for idx, group in enumerate(groups, start=1):
        msg_text = build_single_message(group, templates)
        result.append({
            "id": idx,
            "nome_conta": group.nome_conta,
            "status": group.status,
            "statuses": list(group.statuses),
            "is_multi_status": group.is_multi_status,
            "data_expiracao": group.data_expiracao,
            "tem_datas_diferentes": group.tem_datas_diferentes,
            "quantidade_cnpjs": len(group.itens),
            "itens": [
                {
                    "empresa": it.empresa,
                    "cnpj": it.cnpj,
                    "linha": it.linha_excel,
                    "data_expiracao": it.data_expiracao
                }
                for it in group.itens
            ],
            "mensagem": msg_text,
            "status_configurado": group.status_configurado
        })
    return result


def format_combined_messages(generated_messages: List[Dict[str, Any]]) -> str:
    """Combina todas as mensagens geradas com separadores claros para a função 'Copiar Todas'."""
    divisoria = "\n" + "=" * 60 + "\n\n"
    partes = []

    for msg in generated_messages:
        venc_display = "Datas diferentes" if msg.get("tem_datas_diferentes") else msg["data_expiracao"]
        statuses_display = ", ".join(msg.get("statuses", [msg["status"]]))
        cabecalho_info = (
            f"[{msg['nome_conta']}] - Status: {statuses_display} | Vencimento: {venc_display}\n"
            + "-" * 40
        )
        corpo = f"{cabecalho_info}\n{msg['mensagem']}"
        partes.append(corpo)

    return divisoria.join(partes)
