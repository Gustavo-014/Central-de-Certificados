import unittest
import pandas as pd
from core.template_manager import load_templates
from core.processor import process_dataframe, ProcessingResult
from core.message_builder import build_all_messages
from core.pdf_generator import generate_pdf_report, sanitize_text


class TestPDFGenerator(unittest.TestCase):
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

    def test_sanitize_text(self):
        self.assertEqual(sanitize_text("Teste ✅ OK 🚀"), "Teste  OK")
        self.assertEqual(sanitize_text(None), "")
        self.assertEqual(sanitize_text("Empresa Alfa"), "Empresa Alfa")

    def test_pdf_generation_mixed_status(self):
        # 1 enviada, 1 pendente
        enviados = {
            self.mensagens[0]["nome_conta"]: True,
            self.mensagens[1]["nome_conta"]: False,
        }
        pdf_bytes = generate_pdf_report(
            mensagens=self.mensagens,
            enviados=enviados,
            result=self.result,
            nome_arquivo="teste.xlsx",
            nome_aba="Planilha1"
        )
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_pdf_generation_all_pending(self):
        enviados = {m["nome_conta"]: False for m in self.mensagens}
        pdf_bytes = generate_pdf_report(
            mensagens=self.mensagens,
            enviados=enviados,
            result=self.result,
            nome_arquivo="teste.xlsx",
            nome_aba="Planilha1"
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_pdf_generation_all_sent(self):
        enviados = {m["nome_conta"]: True for m in self.mensagens}
        pdf_bytes = generate_pdf_report(
            mensagens=self.mensagens,
            enviados=enviados,
            result=self.result,
            nome_arquivo="teste.xlsx",
            nome_aba="Planilha1"
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_pdf_generation_with_problematic_records(self):
        self.result.registros_problematicos = [
            {
                "linha": 5,
                "nome_conta": "CONTA INCOMPLETA",
                "empresa": "Incompleta LTDA",
                "cnpj": "000",
                "status": "ENTRAR EM CONTATO",
                "motivos": ["CNPJ inválido"]
            }
        ]
        enviados = {m["nome_conta"]: True for m in self.mensagens}
        pdf_bytes = generate_pdf_report(
            mensagens=self.mensagens,
            enviados=enviados,
            result=self.result,
            nome_arquivo="teste.xlsx",
            nome_aba="Planilha1"
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
