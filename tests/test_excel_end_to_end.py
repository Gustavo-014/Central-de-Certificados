import os
import unittest
from pathlib import Path
import pandas as pd

from core.excel_reader import read_excel
from core.processor import process_dataframe
from core.message_builder import build_all_messages, format_combined_messages
from core.template_manager import load_templates


class TestExcelEndToEnd(unittest.TestCase):
    def setUp(self):
        self.test_excel_path = Path(__file__).parent / "sample_planilha.xlsx"
        self.templates = load_templates()

        # Monta planilha simulada com todos os casos de teste
        dados = [
            # 1 e 2: Mesma conta, mesmo status, mesma data -> devem agrupar em 1 mensagem
            {
                "Nome da Conta": "CONTA ALFA",
                "Empresa": "Minérios Ferreira LTDA",
                "CNPJ": "08.234.078/0001-82",
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS",
                "Outra Coluna Inutil": "ABC"
            },
            {
                "Nome da Conta": "CONTA ALFA",
                "Empresa": "OSCAR VIEIRA FERREIRA LTDA",
                "CNPJ": "89684906000186", # sem máscara e com números
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS",
                "Outra Coluna Inutil": "XYZ"
            },
            # 3: Mesma CONTA ALFA, mas data diferente -> mensagem separada
            {
                "Nome da Conta": "CONTA ALFA",
                "Empresa": "Filial Sul LTDA",
                "CNPJ": "12.345.678/0001-90",
                "Certificado Expira em": "25/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS",
                "Outra Coluna Inutil": "123"
            },
            # 4: CERTIFICADO OK -> deve ser completamente ignorado
            {
                "Nome da Conta": "CONTA BETA",
                "Empresa": "Beta Logística",
                "CNPJ": "11.222.333/0001-44",
                "Certificado Expira em": "10/10/2026",
                "status do fluxo": "CERTIFICADO OK",
                "Outra Coluna Inutil": "OK"
            },
            # 5: Certificado Expirado
            {
                "Nome da Conta": "CONTA GAMA",
                "Empresa": "Gama Transportes",
                "CNPJ": "99.888.777/0001-66",
                "Certificado Expira em": "01/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, CERTIFICADO EXPIRADO",
                "Outra Coluna Inutil": "EXP"
            },
            # 6: Status Desconhecido
            {
                "Nome da Conta": "CONTA DELTA",
                "Empresa": "Delta Distribuidora",
                "CNPJ": "33.444.555/0001-22",
                "Certificado Expira em": "15/10/2026",
                "status do fluxo": "STATUS TESTE NAO CONFIGURADO",
                "Outra Coluna Inutil": "NOVO"
            },
            # 7: Linha com campo incompleto (sem CNPJ)
            {
                "Nome da Conta": "CONTA EPSILON",
                "Empresa": "Epsilon Comércio",
                "CNPJ": "",
                "Certificado Expira em": "20/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 15 DIAS",
                "Outra Coluna Inutil": "ERR"
            }
        ]
        df = pd.DataFrame(dados)
        df.to_excel(self.test_excel_path, index=False)

    def tearDown(self):
        if self.test_excel_path.exists():
            os.remove(self.test_excel_path)

    def test_full_pipeline_from_excel_file(self):
        # 1. Lê a planilha do disco
        df = read_excel(self.test_excel_path)
        self.assertEqual(len(df), 7)

        # 2. Processa
        result = process_dataframe(df, self.templates)

        self.assertEqual(result.total_linhas, 7)
        self.assertEqual(result.total_ok, 1)  # Beta
        self.assertEqual(result.total_acao, 6)
        self.assertEqual(len(result.registros_problematicos), 1)  # Epsilon
        self.assertEqual(result.registros_problematicos[0]["nome_conta"], "CONTA EPSILON")
        self.assertIn("CNPJ vazio", result.registros_problematicos[0]["motivos"])

        self.assertIn("STATUS TESTE NAO CONFIGURADO", result.status_desconhecidos)

        # Mensagens válidas geradas:
        # - CONTA ALFA (mesmo status, datas diferentes: 17/09 e 25/09) -> 3 CNPJs agrupados em 1 mensagem com Vencimento
        # - CONTA GAMA (01/09/2026) -> 1 CNPJ
        # - CONTA DELTA (15/10/2026) -> 1 CNPJ (status desconhecido, marcado)
        self.assertEqual(result.total_mensagens, 3)

        mensagens = build_all_messages(result.grupos, self.templates)
        self.assertEqual(len(mensagens), 3)

        # Verifica agrupamento unificado da CONTA ALFA com datas diferentes e placeholders modulares
        msg_alfa = next(m for m in mensagens if m["nome_conta"] == "CONTA ALFA")
        self.assertEqual(msg_alfa["quantidade_cnpjs"], 3)
        self.assertTrue(msg_alfa["tem_datas_diferentes"])
        bloco_1 = "Cliente: Minérios Ferreira LTDA\nCNPJ: 08.234.078/0001-82\nVencimento: 17/09/2026"
        bloco_2 = "Cliente: OSCAR VIEIRA FERREIRA LTDA\nCNPJ: 89.684.906/0001-86\nVencimento: 17/09/2026"
        bloco_3 = "Cliente: Filial Sul LTDA\nCNPJ: 12.345.678/0001-90\nVencimento: 25/09/2026"
        self.assertIn(f"{bloco_1}\n\n{bloco_2}\n\n{bloco_3}", msg_alfa["mensagem"])

        # Teste de copiar todas
        combined = format_combined_messages(mensagens)
        self.assertIn("CONTA ALFA", combined)
        self.assertIn("CONTA GAMA", combined)
        self.assertIn("Datas diferentes", combined)
        self.assertIn("=" * 60, combined)


if __name__ == "__main__":
    unittest.main()
