import re
import unicodedata
from typing import Any, Dict, List, Tuple
import pandas as pd

REQUIRED_COLUMNS = [
    "Nome da Conta",
    "Empresa",
    "CNPJ",
    "Certificado Expira em",
    "status do fluxo",
]

# Mapeamento canônico (normalizado -> nome oficial esperado pelo sistema)
CANONICAL_COLUMNS = {
    "nome da conta": "Nome da Conta",
    "empresa": "Empresa",
    "cnpj": "CNPJ",
    "certificado expira em": "Certificado Expira em",
    "status do fluxo": "status do fluxo",
}

# Sinônimos comuns aceitos para máxima tolerância
ALIASES = {
    "conta": "Nome da Conta",
    "nome conta": "Nome da Conta",
    "cliente": "Empresa",
    "razao social": "Empresa",
    "nome empresa": "Empresa",
    "expira em": "Certificado Expira em",
    "data de expiracao": "Certificado Expira em",
    "data expiracao": "Certificado Expira em",
    "vencimento": "Certificado Expira em",
    "data vencimento": "Certificado Expira em",
    "status": "status do fluxo",
    "status fluxo": "status do fluxo",
}


def normalize_header(header: Any) -> str:
    """Normaliza o nome do cabeçalho removendo quebras de linha, acentos, 
    espaços múltiplos e caracteres especiais para comparação flexível.
    """
    if header is None:
        return ""
    text = str(header)
    # Substitui espaços não quebráveis, quebras de linha (\n, \r) por espaço comum
    text = text.replace("\xa0", " ").replace("\r", " ").replace("\n", " ")
    # Remove acentos
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Remove pontuações e símbolos, mantendo letras, números e espaços
    text = re.sub(r"[^\w\s]", "", text)
    # Colapsa múltiplos espaços em um único e deixa em minúsculas
    return re.sub(r"\s+", " ", text).strip().lower()


def detect_and_map_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str], List[str]]:
    """Identifica as 5 colunas obrigatórias no DataFrame, renomeia para os nomes canônicos
    e retorna: (df_renomeado, colunas_mapeadas, colunas_ausentes).
    """
    matched = {}
    remaining_canonical = dict(CANONICAL_COLUMNS)

    # Passo 1: Comparação direta pelo nome normalizado
    for col in df.columns:
        norm = normalize_header(col)
        if norm in remaining_canonical:
            matched[col] = remaining_canonical[norm]
            del remaining_canonical[norm]

    # Passo 2: Comparação por sinônimos/aliases caso ainda falte alguma coluna
    if remaining_canonical:
        for col in df.columns:
            if col in matched:
                continue
            norm = normalize_header(col)
            if norm in ALIASES and ALIASES[norm] in remaining_canonical.values():
                canon = ALIASES[norm]
                for k, v in list(remaining_canonical.items()):
                    if v == canon:
                        matched[col] = canon
                        del remaining_canonical[k]
                        break

    missing = list(remaining_canonical.values())
    renamed_df = df.rename(columns=matched)
    return renamed_df, matched, missing


def clean_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza e renomeia as colunas do DataFrame para os nomes canônicos."""
    renamed_df, _, _ = detect_and_map_columns(df)
    return renamed_df


def validate_columns(dataframe: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Valida se o DataFrame possui as 5 colunas obrigatórias.
    
    Retorna uma tupla (valido: bool, colunas_ausentes: List[str]).
    """
    _, _, missing_columns = detect_and_map_columns(dataframe)
    return (len(missing_columns) == 0, missing_columns)


def check_record_completeness(record: Dict[str, Any], row_number: int) -> Tuple[bool, List[str]]:
    """Verifica se um registro possui todos os campos obrigatórios preenchidos."""
    missing_fields = []

    for field in ["Nome da Conta", "Empresa", "CNPJ", "Certificado Expira em"]:
        val = record.get(field)
        if val is None or pd.isna(val) or str(val).strip() in ["", "nan", "None", "NaT"]:
            missing_fields.append(field)

    return (len(missing_fields) == 0, missing_fields)
