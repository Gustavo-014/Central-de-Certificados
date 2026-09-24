import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


def get_templates_path() -> Path:
    """Retorna o caminho do arquivo data/templates.json."""
    return Path(__file__).resolve().parent.parent / "data" / "templates.json"


def normalize_status(status: Any) -> str:
    """Normaliza uma string de status (espaços, maiúsculas)."""
    if status is None:
        return ""
    text = str(status).strip().upper()
    # Substitui múltiplos espaços por um único espaço
    return re.sub(r"\s+", " ", text)


def load_templates() -> Dict[str, Dict[str, str]]:
    """Carrega os templates cadastrados no arquivo templates.json."""
    templates_path = get_templates_path()
    if not templates_path.exists():
        return {}

    with templates_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_templates(templates: Dict[str, Dict[str, str]]) -> None:
    """Salva os templates atualizados no arquivo templates.json."""
    templates_path = get_templates_path()
    templates_path.parent.mkdir(parents=True, exist_ok=True)

    with templates_path.open("w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)


def get_template_text(status: str, templates: Dict[str, Any]) -> Optional[str]:
    """Busca o texto do template correspondente ao status normalizado."""
    norm_status = normalize_status(status)

    for key, data in templates.items():
        if normalize_status(key) == norm_status:
            if isinstance(data, dict):
                return data.get("template", "")
            if isinstance(data, str):
                return data

    return None
