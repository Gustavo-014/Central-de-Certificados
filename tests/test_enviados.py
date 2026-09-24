import unittest
from typing import Dict, Any, List
import pandas as pd

from core.processor import process_dataframe
from core.message_builder import build_all_messages
from core.template_manager import load_templates


class TestEnviadosControl(unittest.TestCase):
    def setUp(self):
        self.templates = load_templates()
        self.data = [
            {
                "Nome da Conta": "CONTA ALFA",
                "Empresa": "Alfa Minerios",
                "CNPJ": "11.111.111/0001-11",
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, CERTIFICADO EXPIRADO"
            },
            {
                "Nome da Conta": "CONTA BETA",
                "Empresa": "Beta Logistica",
                "CNPJ": "22.222.222/0001-22",
                "Certificado Expira em": "20/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            }
        ]
        self.df = pd.DataFrame(self.data)
        self.result = process_dataframe(self.df, self.templates)
        self.mensagens = build_all_messages(self.result.grupos, self.templates)

    def test_message_keys_unique(self):
        keys = [f"{m['nome_conta']}___{m['status']}" for m in self.mensagens]
        self.assertEqual(len(keys), len(set(keys)))

    def test_enviados_tracking_and_title_formatting(self):
        enviados: Dict[str, bool] = {}

        # Inicializa pendentes
        for m in self.mensagens:
            m_key = f"{m['nome_conta']}___{m['status']}"
            enviados[m_key] = False

        # Verifica titulos no estado pendente
        for m in self.mensagens:
            m_key = f"{m['nome_conta']}___{m['status']}"
            is_enviado = enviados[m_key]
            venc = m["data_expiracao"]
            if is_enviado:
                titulo = f"[ENVIADO] {m['nome_conta']} | Vencimento: {venc}"
            else:
                titulo = f"{m['nome_conta']} | Vencimento: {venc}"
            
            self.assertFalse(is_enviado)
            self.assertNotIn("[ENVIADO]", titulo)

        # Marca a primeira mensagem como enviada
        primeira_key = f"{self.mensagens[0]['nome_conta']}___{self.mensagens[0]['status']}"
        enviados[primeira_key] = True

        # Total enviados
        total_enviados = sum(1 for v in enviados.values() if v)
        self.assertEqual(total_enviados, 1)

        # Verifica titulos com a primeira enviada
        for m in self.mensagens:
            m_key = f"{m['nome_conta']}___{m['status']}"
            is_enviado = enviados[m_key]
            venc = m["data_expiracao"]
            if is_enviado:
                titulo = f"CHECK {m['nome_conta']} | Vencimento: {venc} - [ENVIADO]"
                expanded = not is_enviado
            else:
                titulo = f"BUILDING {m['nome_conta']} | Vencimento: {venc}"
                expanded = not is_enviado

            if m_key == primeira_key:
                self.assertTrue(is_enviado)
                self.assertFalse(expanded)
                self.assertIn("[ENVIADO]", titulo)
            else:
                self.assertFalse(is_enviado)
                self.assertTrue(expanded)
                self.assertNotIn("[ENVIADO]", titulo)

    def test_filter_by_enviado_status(self):
        enviados = {
            f"{self.mensagens[0]['nome_conta']}___{self.mensagens[0]['status']}": True,
            f"{self.mensagens[1]['nome_conta']}___{self.mensagens[1]['status']}": False,
        }

        # Filtro: Apenas Pendentes
        pendentes = [
            m for m in self.mensagens
            if not enviados.get(f"{m['nome_conta']}___{m['status']}", False)
        ]
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0]["nome_conta"], "CONTA BETA")

        # Filtro: Apenas Enviados
        enviados_list = [
            m for m in self.mensagens
            if enviados.get(f"{m['nome_conta']}___{m['status']}", False)
        ]
        self.assertEqual(len(enviados_list), 1)
        self.assertEqual(enviados_list[0]["nome_conta"], "CONTA ALFA")


if __name__ == "__main__":
    unittest.main()
