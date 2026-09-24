import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from core.template_manager import normalize_status
from core.validator import clean_dataframe_columns, validate_columns


@dataclass
class GroupItem:
    empresa: str
    cnpj: str
    linha_excel: int
    data_expiracao: str


@dataclass
class StatusSubGroup:
    """Sub-grupo de itens com o mesmo status dentro de uma conta."""
    status: str
    status_normalizado: str
    status_configurado: bool
    itens: List[GroupItem] = field(default_factory=list)


@dataclass
class CertificateGroup:
    nome_conta: str
    status: str  # Status principal (mais urgente) ou único
    status_normalizado: str
    data_expiracao: str
    tem_datas_diferentes: bool = False
    itens: List[GroupItem] = field(default_factory=list)
    status_configurado: bool = True
    # Campos para suporte a múltiplos status por cliente
    is_multi_status: bool = False
    statuses: List[str] = field(default_factory=list)
    sub_groups: List["StatusSubGroup"] = field(default_factory=list)


@dataclass
class ProcessingResult:
    total_linhas: int
    total_ok: int
    total_acao: int
    total_mensagens: int
    por_status: Dict[str, int]
    status_desconhecidos: List[str]
    registros_problematicos: List[Dict[str, Any]]
    grupos: List[CertificateGroup]


def format_cnpj(val: Any) -> str:
    """Formata o CNPJ garantindo 14 dígitos com máscara XX.XXX.XXX/XXXX-XX."""
    if val is None or pd.isna(val):
        return ""

    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]

    # Extrai apenas os dígitos
    digits = re.sub(r"\D", "", val_str)

    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
    elif 0 < len(digits) < 14:
        # Preenche zeros à esquerda caso o Excel tenha descartado
        digits = digits.zfill(14)
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"

    return val_str


def parse_brazilian_date(val: Any) -> Tuple[Optional[str], Optional[str]]:
    """Converte valores variados em uma data no formato brasileiro DD/MM/AAAA.
    
    Retorna (data_formatada, erro).
    """
    if val is None or pd.isna(val):
        return None, "Data vazia ou nula"

    val_str = str(val).strip()
    if not val_str or val_str.lower() in ["nan", "none", "nat", "null"]:
        return None, "Data vazia"

    # Se já é objeto datetime do Python ou Pandas Timestamp
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.strftime("%d/%m/%Y"), None

    # Tenta padrão brasileiro com regex: DD/MM/AAAA ou D/M/AAAA
    match_br = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", val_str)
    if match_br:
        day, month, year = int(match_br.group(1)), int(match_br.group(2)), int(match_br.group(3))
        try:
            dt = datetime(year, month, day)
            return dt.strftime("%d/%m/%Y"), None
        except ValueError:
            return None, f"Data inválida ({val_str})"

    # Tenta padrão ISO com regex: YYYY-MM-DD
    match_iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", val_str)
    if match_iso:
        year, month, day = int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3))
        try:
            dt = datetime(year, month, day)
            return dt.strftime("%d/%m/%Y"), None
        except ValueError:
            return None, f"Data inválida ({val_str})"

    # Se for número serial do Excel (ex: 45000)
    if re.match(r"^\d+(\.\d+)?$", val_str):
        try:
            num = float(val_str)
            if 30000 < num < 70000:
                dt = pd.to_datetime(num, unit="D", origin="1899-12-30")
                return dt.strftime("%d/%m/%Y"), None
        except Exception:
            pass

    # Tenta parsing genérico com pandas considerando dia primeiro
    try:
        dt = pd.to_datetime(val_str, dayfirst=True)
        return dt.strftime("%d/%m/%Y"), None
    except Exception:
        return None, f"Formato de data inválido ({val_str})"


def get_status_priority(status_norm: str) -> int:
    """Retorna prioridade do status (menor = mais urgente).

    Usado para determinar o status principal em grupos multi-status.
    """
    priorities = {
        "ENTRAR EM CONTATO, CERTIFICADO EXPIRADO": 1,
        "ENTRAR EM CONTATO, EXPIRA HOJE!": 2,
        "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS": 3,
        "ENTRAR EM CONTATO, EXPIRA EM 15 DIAS": 4,
        "CERTIFICADO EXPIRA EM 30 DIAS": 5,
    }
    return priorities.get(status_norm, 99)


def process_dataframe(
    df: pd.DataFrame,
    templates: Dict[str, Any]
) -> ProcessingResult:
    """Processa o DataFrame da planilha de certificados digitais.
    
    Aplica:
    1. Limpeza de colunas e validação.
    2. Ignora registros onde 'status do fluxo' for 'CERTIFICADO OK'.
    3. Normalização de CNPJ e data DD/MM/AAAA.
    4. Identificação de status desconhecidos e linhas incompletas.
    5. Agrupamento por Nome da Conta (unificando todos os status do mesmo cliente).
    """
    cleaned_df = clean_dataframe_columns(df)
    is_valid, missing_cols = validate_columns(cleaned_df)
    if not is_valid:
        raise ValueError(f"Planilha inválida. Colunas ausentes: {', '.join(missing_cols)}")

    # Templates conhecidos normalizados
    known_statuses = {normalize_status(k) for k in templates.keys()}

    total_linhas = len(cleaned_df)
    total_ok = 0
    total_acao = 0
    por_status: Dict[str, int] = {}
    status_desconhecidos_set = set()
    registros_problematicos: List[Dict[str, Any]] = []

    # Dicionário de agrupamento principal: chave = nome_conta
    groups_dict: Dict[str, CertificateGroup] = {}
    # Dicionário auxiliar de sub-grupos: chave = (nome_conta, status_normalizado)
    sub_groups_dict: Dict[Tuple[str, str], StatusSubGroup] = {}

    for idx, row in cleaned_df.iterrows():
        linha_excel = idx + 2  # Cabeçalho na linha 1

        nome_conta = str(row.get("Nome da Conta") or "").strip()
        empresa = str(row.get("Empresa") or "").strip()
        cnpj_raw = row.get("CNPJ")
        data_raw = row.get("Certificado Expira em")
        status_raw = str(row.get("status do fluxo") or "").strip()
        status_norm = normalize_status(status_raw)

        # Regra 1: CERTIFICADO OK é completamente ignorado
        if status_norm == "CERTIFICADO OK":
            total_ok += 1
            por_status["CERTIFICADO OK"] = por_status.get("CERTIFICADO OK", 0) + 1
            continue

        # Registro que precisa de ação
        total_acao += 1
        por_status[status_raw] = por_status.get(status_raw, 0) + 1

        # Validação de campos obrigatórios
        erros_linha = []
        if not nome_conta:
            erros_linha.append("Nome da Conta vazio")
        if not empresa:
            erros_linha.append("Empresa vazia")
        if cnpj_raw is None or pd.isna(cnpj_raw) or str(cnpj_raw).strip() == "":
            erros_linha.append("CNPJ vazio")
        if data_raw is None or pd.isna(data_raw) or str(data_raw).strip() == "":
            erros_linha.append("Data de expiração vazia")

        data_formatada, erro_data = parse_brazilian_date(data_raw)
        if erro_data and "Data de expiração vazia" not in erros_linha:
            erros_linha.append(erro_data)

        # Se houver dados incompletos ou inválidos, adiciona aos registros problemáticos
        if erros_linha:
            registros_problematicos.append({
                "linha": linha_excel,
                "nome_conta": nome_conta or "(Não preenchido)",
                "empresa": empresa or "(Não preenchido)",
                "cnpj": str(cnpj_raw) if cnpj_raw is not None else "",
                "status": status_raw,
                "motivos": erros_linha
            })
            continue

        # Verifica se o status está configurado
        is_configurado = status_norm in known_statuses
        if not is_configurado:
            status_desconhecidos_set.add(status_raw)

        cnpj_formatado = format_cnpj(cnpj_raw)

        # Chave de Agrupamento principal: apenas Nome da Conta
        group_key = nome_conta

        if group_key not in groups_dict:
            groups_dict[group_key] = CertificateGroup(
                nome_conta=nome_conta,
                status=status_raw,
                status_normalizado=status_norm,
                data_expiracao="",
                tem_datas_diferentes=False,
                itens=[],
                status_configurado=is_configurado
            )

        # Sub-grupo por status dentro da mesma conta
        sub_key = (nome_conta, status_norm)
        if sub_key not in sub_groups_dict:
            sub_groups_dict[sub_key] = StatusSubGroup(
                status=status_raw,
                status_normalizado=status_norm,
                status_configurado=is_configurado,
                itens=[]
            )

        # Evita duplicar exatamente a mesma Empresa + CNPJ + Data dentro do mesmo sub-grupo
        item_existente = any(
            item.empresa == empresa and item.cnpj == cnpj_formatado and item.data_expiracao == data_formatada
            for item in sub_groups_dict[sub_key].itens
        )
        if not item_existente:
            sub_groups_dict[sub_key].itens.append(GroupItem(
                empresa=empresa,
                cnpj=cnpj_formatado,
                linha_excel=linha_excel,
                data_expiracao=data_formatada
            ))

    # Monta sub-grupos e lista flat de itens para cada grupo principal
    for nome, grupo in groups_dict.items():
        # Coleta todos os sub-grupos desta conta, ordenados por urgência
        account_sub_groups = [
            sg for (acc_name, _), sg in sub_groups_dict.items()
            if acc_name == nome
        ]
        account_sub_groups.sort(key=lambda sg: get_status_priority(sg.status_normalizado))

        grupo.sub_groups = account_sub_groups
        grupo.statuses = [sg.status for sg in account_sub_groups]
        grupo.is_multi_status = len(account_sub_groups) > 1

        # Status principal = o mais urgente
        if account_sub_groups:
            grupo.status = account_sub_groups[0].status
            grupo.status_normalizado = account_sub_groups[0].status_normalizado
            grupo.status_configurado = all(sg.status_configurado for sg in account_sub_groups)

        # Lista flat de itens (agregada de todos os sub-grupos, na ordem de urgência)
        grupo.itens = []
        for sg in account_sub_groups:
            grupo.itens.extend(sg.itens)

        # Define a data de expiração do grupo e se há datas diferentes
        datas_unicas = list(dict.fromkeys(it.data_expiracao for it in grupo.itens))
        if len(datas_unicas) == 1:
            grupo.data_expiracao = datas_unicas[0]
            grupo.tem_datas_diferentes = False
        elif len(datas_unicas) > 1:
            grupo.data_expiracao = "datas diferentes"
            grupo.tem_datas_diferentes = True
        else:
            grupo.data_expiracao = ""
            grupo.tem_datas_diferentes = False

    grupos_ordenados = sorted(
        groups_dict.values(),
        key=lambda g: (g.nome_conta.lower(), get_status_priority(g.status_normalizado))
    )

    return ProcessingResult(
        total_linhas=total_linhas,
        total_ok=total_ok,
        total_acao=total_acao,
        total_mensagens=len(grupos_ordenados),
        por_status=por_status,
        status_desconhecidos=sorted(list(status_desconhecidos_set)),
        registros_problematicos=registros_problematicos,
        grupos=grupos_ordenados
    )

