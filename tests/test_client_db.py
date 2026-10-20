import os
import tempfile
import unittest
import warnings
from unittest.mock import patch

# Python 3.14 emite ResourceWarning para conexões SQLite que o GC fecha —
# é comportamento esperado no nosso context manager, não é bug.
warnings.filterwarnings("ignore", category=ResourceWarning)


from core.client_db import (
    delete_client_contact,
    get_all_contacts,
    get_client_contact,
    get_db_path,
    init_contacts_db,
    save_client_contact,
)
from core.whatsapp_desktop import open_group_in_whatsapp_desktop


class TestClientDb(unittest.TestCase):
    def setUp(self):
        # Cria um banco de dados temporário isolado para testes
        self.tmp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.tmp_dir, "test_contacts.db")
        self.env_patch = patch.dict(os.environ, {"CONTACTS_DB_PATH": self.test_db_path})
        self.env_patch.start()
        init_contacts_db()

    def tearDown(self):
        self.env_patch.stop()
        # Fecha qualquer conexão SQLite pendente antes de deletar no Windows
        import gc
        import sqlite3
        gc.collect()
        import shutil
        try:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        except Exception:
            pass

    def test_db_path_and_init(self):
        self.assertEqual(get_db_path(), self.test_db_path)
        self.assertTrue(os.path.exists(self.test_db_path))

    def test_save_and_get_exact(self):
        ok, msg = save_client_contact("EMBALATEC - SNE", "Embalatec & Brobot")
        self.assertTrue(ok)
        contact = get_client_contact("EMBALATEC - SNE")
        self.assertIsNotNone(contact)
        self.assertEqual(contact["contact_value"], "Embalatec & Brobot")
        self.assertEqual(contact["contact_type"], "group_name")

    def test_get_case_insensitive_and_whitespace(self):
        save_client_contact("EMBALATEC - SNE", "Embalatec & Brobot")
        contact = get_client_contact("  embalatec - sne  ")
        self.assertIsNotNone(contact)
        self.assertEqual(contact["contact_value"], "Embalatec & Brobot")

    def test_get_normalized_suffix(self):
        save_client_contact("EMBALATEC - SNE", "Embalatec & Brobot")
        # Busca sem o sufixo "- SNE"
        contact = get_client_contact("EMBALATEC")
        self.assertIsNotNone(contact)
        self.assertEqual(contact["contact_value"], "Embalatec & Brobot")

    def test_save_update_existing(self):
        save_client_contact("CLIENTE X", "Grupo Antigo")
        save_client_contact("CLIENTE X", "Grupo Novo")
        contact = get_client_contact("CLIENTE X")
        self.assertEqual(contact["contact_value"], "Grupo Novo")

    def test_delete_contact(self):
        save_client_contact("CLIENTE DEL", "Grupo Del")
        self.assertIsNotNone(get_client_contact("CLIENTE DEL"))
        ok, msg = delete_client_contact("CLIENTE DEL")
        self.assertTrue(ok)
        self.assertIsNone(get_client_contact("CLIENTE DEL"))

    def test_get_all_contacts(self):
        save_client_contact("CLIENTE A", "Grupo A")
        save_client_contact("CLIENTE B", "Grupo B")
        all_c = get_all_contacts()
        self.assertIn("CLIENTE A", all_c)
        self.assertIn("CLIENTE B", all_c)


class TestWhatsAppDesktop(unittest.TestCase):
    def test_empty_group_name(self):
        ok, msg = open_group_in_whatsapp_desktop("")
        self.assertFalse(ok)
        self.assertIn("Nome do grupo não informado", msg)

        ok, msg = open_group_in_whatsapp_desktop("   ")
        self.assertFalse(ok)

    @patch("core.whatsapp_desktop.pyautogui")
    @patch("core.whatsapp_desktop.pyperclip")
    @patch("core.whatsapp_desktop.time.sleep")
    def test_open_group_flow_success(self, mock_sleep, mock_clip, mock_gui):
        ok, msg = open_group_in_whatsapp_desktop("Grupo Teste", "Mensagem de Cobrança")
        self.assertTrue(ok)
        self.assertIn("Grupo Teste", msg)
        mock_gui.hotkey.assert_any_call("win", "4")
        mock_gui.press.assert_any_call("enter")


if __name__ == "__main__":
    unittest.main()
