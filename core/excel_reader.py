from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from core.validator import detect_and_map_columns


def get_excel_file_bytes(uploaded_file: Union[Any, str, Path, BytesIO]) -> BytesIO:
    """Obtém um BytesIO a partir do arquivo enviado ou caminho."""
    if hasattr(uploaded_file, "getvalue"):
        return BytesIO(uploaded_file.getvalue())
    if isinstance(uploaded_file, (str, Path)):
        with open(uploaded_file, "rb") as f:
            return BytesIO(f.read())
    if isinstance(uploaded_file, BytesIO):
        uploaded_file.seek(0)
        return uploaded_file
    raise ValueError("Arquivo inválido.")


def get_sheet_names(uploaded_file: Union[Any, str, Path, BytesIO]) -> List[str]:
    """Retorna os nomes de todas as abas (planilhas) do arquivo Excel."""
    bio = get_excel_file_bytes(uploaded_file)
    try:
        xl = pd.ExcelFile(bio, engine="openpyxl")
        return xl.sheet_names
    except Exception:
        try:
            bio.seek(0)
            xl = pd.ExcelFile(bio)
            return xl.sheet_names
        except Exception as exc:
            raise ValueError(f"Não foi possível ler as abas do Excel: {exc}") from exc


def inspect_sheet_headers(
    bio: BytesIO, sheet_name: str
) -> Tuple[int, pd.DataFrame, Dict[str, str], List[str]]:
    """Testa as primeiras 5 linhas de uma aba para encontrar a linha de cabeçalhos correta.
    
    Retorna: (header_row_index, df_renomeado, colunas_mapeadas, colunas_ausentes).
    """
    best_match_count = -1
    best_result = (0, pd.DataFrame(), {}, [])

    for h_row in range(5):
        try:
            bio.seek(0)
            df_candidate = pd.read_excel(bio, sheet_name=sheet_name, header=h_row, dtype=str)
            renamed_df, matched, missing = detect_and_map_columns(df_candidate)
            match_count = len(matched)

            if match_count > best_match_count:
                best_match_count = match_count
                best_result = (h_row, renamed_df, matched, missing)

            # Se achou todas as 5 colunas, não precisa testar mais linhas
            if match_count == 5:
                break
        except Exception:
            continue

    return best_result


def read_excel_smart(
    uploaded_file: Union[Any, str, Path, BytesIO],
    sheet_name: Optional[str] = None
) -> Tuple[pd.DataFrame, str, int, Dict[str, str], List[str], List[str]]:
    """Lê a planilha de forma inteligente:
    1. Lista todas as abas.
    2. Se a aba não for especificada, procura a aba que contém as colunas necessárias.
    3. Detecta a linha de cabeçalho correta (0 a 4).
    4. Mapeia e renomeia as colunas para o padrão do sistema.
    
    Retorna:
    (df, sheet_name_usado, header_row_usado, matched_cols, missing_cols, todas_as_abas).
    """
    bio = get_excel_file_bytes(uploaded_file)
    all_sheets = get_sheet_names(uploaded_file)

    if not all_sheets:
        raise ValueError("O arquivo Excel não contém nenhuma planilha/aba.")

    # Se o usuário especificou a aba
    if sheet_name and sheet_name in all_sheets:
        h_row, renamed_df, matched, missing = inspect_sheet_headers(bio, sheet_name)
        return renamed_df, sheet_name, h_row, matched, missing, all_sheets

    # Se não especificou, procura qual aba tem mais colunas reconhecidas
    best_sheet = all_sheets[0]
    best_h_row = 0
    best_df = pd.DataFrame()
    best_matched = {}
    best_missing = []
    max_matched_count = -1

    for s_name in all_sheets:
        h_row, renamed_df, matched, missing = inspect_sheet_headers(bio, s_name)
        if len(matched) > max_matched_count:
            max_matched_count = len(matched)
            best_sheet = s_name
            best_h_row = h_row
            best_df = renamed_df
            best_matched = matched
            best_missing = missing

        if max_matched_count == 5:
            break

    return best_df, best_sheet, best_h_row, best_matched, best_missing, all_sheets


def read_excel(uploaded_file: Union[Any, str, Path, BytesIO]) -> pd.DataFrame:
    """Função legada de leitura de Excel para retrocompatibilidade."""
    df, _, _, _, _, _ = read_excel_smart(uploaded_file)
    return df
