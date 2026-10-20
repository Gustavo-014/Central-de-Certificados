import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Dict, Optional, Tuple

# Banco de dados local do projeto
_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "contacts.db"
)

# Banco compartilhado do Central de Erros (fonte de sincronização)
_SHARED_DB = r"c:\Gustavo\Central de Erros\data\history.db"


def get_db_path() -> str:
    """Retorna o caminho do banco SQLite local de contatos/grupos."""
    # Variável de ambiente permite sobrescrever em testes ou deploys alternativos
    return os.environ.get("CONTACTS_DB_PATH", _DB_PATH)


@contextmanager
def _get_conn():
    """Context manager que abre, entrega e fecha a conexão corretamente."""
    path = get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_contacts_db() -> None:
    """Garante que a tabela client_contacts exista no banco de dados local."""
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS client_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT UNIQUE NOT NULL,
                contact_type TEXT NOT NULL DEFAULT 'group_name',
                contact_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_client_name ON client_contacts(client_name)"
        )


def _normalize_name(name: str) -> str:
    """Remove sufixos operacionais conhecidos para correspondência flexível."""
    if not name:
        return ""
    n = name.strip().upper()
    n = re.sub(r"\s*-\s*(SNE|APPELSOFT|ABE3|BLOQUEADA).*$", "", n)
    return n.strip()


def get_client_contact(client_name: str) -> Optional[Dict[str, str]]:
    """
    Busca o grupo/contato cadastrado para o cliente.
    Aplica correspondência em 4 níveis:
      1. Exata
      2. Case-insensitive + trim
      3. Nome normalizado (sem sufixos como '- SNE')
      4. Prefixo (LIKE 'NOME%')
    """
    if not client_name or not str(client_name).strip():
        return None

    raw = str(client_name).strip()
    init_contacts_db()

    with _get_conn() as conn:
        q = "SELECT client_name, contact_type, contact_value, updated_at FROM client_contacts"

        # 1. Exata
        row = conn.execute(f"{q} WHERE client_name = ?", (raw,)).fetchone()
        if row:
            return dict(row)

        # 2. Case-insensitive
        row = conn.execute(
            f"{q} WHERE LOWER(TRIM(client_name)) = LOWER(TRIM(?))", (raw,)
        ).fetchone()
        if row:
            return dict(row)

        # 3. Normalizado (sem sufixos)
        norm = _normalize_name(raw)
        if norm and norm != raw.upper():
            row = conn.execute(
                f"{q} WHERE LOWER(TRIM(client_name)) = LOWER(TRIM(?))", (norm,)
            ).fetchone()
            if row:
                return dict(row)

            # Compara todos os cadastrados normalizados
            for r in conn.execute(q).fetchall():
                if _normalize_name(r["client_name"]) == norm:
                    return dict(r)

        # 4. Prefixo
        row = conn.execute(
            f"{q} WHERE client_name LIKE ? ORDER BY LENGTH(client_name) ASC LIMIT 1",
            (f"{norm}%",),
        ).fetchone()
        if row:
            return dict(row)

        return None


def save_client_contact(
    client_name: str, contact_value: str, contact_type: str = "group_name"
) -> Tuple[bool, str]:
    """Cadastra ou atualiza o grupo/contato de um cliente."""
    init_contacts_db()
    c_name = str(client_name).strip()
    c_val = str(contact_value).strip()

    if not c_name:
        return False, "O nome do cliente não pode estar vazio."
    if not c_val:
        return False, "O nome do grupo ou contato não pode estar vazio."

    # Detecção automática de link de grupo
    if contact_type == "group_name" and (
        "chat.whatsapp.com" in c_val.lower() or c_val.startswith("http")
    ):
        contact_type = "group_link"

    try:
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO client_contacts (client_name, contact_type, contact_value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(client_name) DO UPDATE SET
                    contact_type = excluded.contact_type,
                    contact_value = excluded.contact_value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (c_name, contact_type, c_val),
            )
        return True, f"Grupo '{c_val}' vinculado ao cliente '{c_name}' com sucesso!"
    except Exception as e:
        return False, f"Erro ao salvar contato: {str(e)}"


def delete_client_contact(client_name: str) -> Tuple[bool, str]:
    """Remove o grupo/contato cadastrado de um cliente."""
    if not client_name or not str(client_name).strip():
        return False, "Nome do cliente inválido."

    init_contacts_db()
    try:
        with _get_conn() as conn:
            conn.execute(
                "DELETE FROM client_contacts WHERE client_name = ?",
                (client_name.strip(),),
            )
        return True, f"Contato de '{client_name}' removido com sucesso."
    except Exception as e:
        return False, f"Erro ao excluir contato: {str(e)}"


def get_all_contacts() -> Dict[str, Dict[str, str]]:
    """Retorna todos os contatos ordenados alfabeticamente."""
    init_contacts_db()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT client_name, contact_type, contact_value, updated_at "
            "FROM client_contacts ORDER BY client_name COLLATE NOCASE ASC"
        ).fetchall()
    return {
        row["client_name"]: {
            "contact_type": row["contact_type"],
            "contact_value": row["contact_value"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    }


def sync_from_central_de_erros(
    shared_db_path: str = _SHARED_DB,
    overwrite_local: bool = False,
) -> Tuple[bool, str, int, int]:
    """
    Copia os contatos da tabela client_contacts do Central de Erros
    para o banco local deste projeto.

    Regras:
    - Se overwrite_local=False (padrão): só importa clientes que ainda NÃO existem
      localmente. Preserva edições feitas aqui.
    - Se overwrite_local=True: substitui tudo, inclusive registros já editados aqui.

    Retorna: (sucesso, mensagem, novos_importados, ja_existentes)
    """
    if not os.path.exists(shared_db_path):
        return (
            False,
            f"Banco do Central de Erros não encontrado em:\n`{shared_db_path}`",
            0,
            0,
        )

    init_contacts_db()

    try:
        # Lê os dados da origem
        src_conn = sqlite3.connect(shared_db_path)
        src_conn.row_factory = sqlite3.Row
        src_rows = src_conn.execute(
            "SELECT client_name, contact_type, contact_value, updated_at FROM client_contacts"
        ).fetchall()
        src_conn.close()

        novos = 0
        existentes = 0

        with _get_conn() as conn:
            for row in src_rows:
                if overwrite_local:
                    conn.execute(
                        """
                        INSERT INTO client_contacts
                            (client_name, contact_type, contact_value, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(client_name) DO UPDATE SET
                            contact_type  = excluded.contact_type,
                            contact_value = excluded.contact_value,
                            updated_at    = excluded.updated_at
                        """,
                        (row["client_name"], row["contact_type"],
                         row["contact_value"], row["updated_at"]),
                    )
                    novos += 1
                else:
                    # Verifica se já existe localmente
                    exists = conn.execute(
                        "SELECT 1 FROM client_contacts WHERE client_name = ?",
                        (row["client_name"],),
                    ).fetchone()
                    if exists:
                        existentes += 1
                    else:
                        conn.execute(
                            """
                            INSERT INTO client_contacts
                                (client_name, contact_type, contact_value, updated_at)
                            VALUES (?, ?, ?, ?)
                            """,
                            (row["client_name"], row["contact_type"],
                             row["contact_value"], row["updated_at"]),
                        )
                        novos += 1

        if overwrite_local:
            msg = f"Sincronização completa: **{novos}** grupos importados (modo substituição total)."
        else:
            msg = (
                f"Sincronização concluída: **{novos}** novos grupos importados, "
                f"**{existentes}** já existiam localmente (mantidos sem alteração)."
            )

        return True, msg, novos, existentes

    except Exception as e:
        return False, f"Erro durante a sincronização: {str(e)}", 0, 0
