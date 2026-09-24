import unittest
import pandas as pd

from core.validator import validate_columns, clean_dataframe_columns
from core.template_manager import load_templates, normalize_status, get_template_text
from core.processor import process_dataframe, format_cnpj, parse_brazilian_date
from core.message_builder import build_single_message, build_all_messages, format_combined_messages


class TestCertificateProcessor(unittest.TestCase):

    def setUp(self):
        self.templates = load_templates()

    def test_validate_columns_success(self):
        df = pd.DataFrame(columns=[
            "Nome da Conta", "Empresa", "CNPJ", "Certificado Expira em", "status do fluxo"
        ])
        is_valid, missing = validate_columns(df)
        self.assertTrue(is_valid)
        self.assertEqual(missing, [])

    def test_validate_columns_missing(self):
        df = pd.DataFrame(columns=["Nome da Conta", "Empresa", "CNPJ"])
        is_valid, missing = validate_columns(df)
        self.assertFalse(is_valid)
        self.assertIn("Certificado Expira em", missing)
        self.assertIn("status do fluxo", missing)

    def test_format_cnpj(self):
        # 14 dígitos sem máscara
        self.assertEqual(format_cnpj("08234078000182"), "08.234.078/0001-82")
        # 13 dígitos (sem zero à esquerda)
        self.assertEqual(format_cnpj("8234078000182"), "08.234.078/0001-82")
        # Já formatado
        self.assertEqual(format_cnpj("89.684.906/0001-86"), "89.684.906/0001-86")
        # Flutuante vindo do excel
        self.assertEqual(format_cnpj("8234078000182.0"), "08.234.078/0001-82")

    def test_parse_brazilian_date(self):
        # DD/MM/AAAA
        dt_str, err = parse_brazilian_date("17/09/2026")
        self.assertEqual(dt_str, "17/09/2026")
        self.assertIsNone(err)

        # ISO YYYY-MM-DD
        dt_str, err = parse_brazilian_date("2026-09-17")
        self.assertEqual(dt_str, "17/09/2026")
        self.assertIsNone(err)

        # Data vazia ou inválida
        dt_str, err = parse_brazilian_date("")
        self.assertIsNone(dt_str)
        self.assertIsNotNone(err)

    def test_ignore_certificado_ok(self):
        data = [
            {
                "Nome da Conta": "CONTA 1",
                "Empresa": "Empresa A",
                "CNPJ": "08.234.078/0001-82",
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "CERTIFICADO OK"
            },
            {
                "Nome da Conta": "CONTA 2",
                "Empresa": "Empresa B",
                "CNPJ": "89.684.906/0001-86",
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            }
        ]
        df = pd.DataFrame(data)
        result = process_dataframe(df, self.templates)

        self.assertEqual(result.total_linhas, 2)
        self.assertEqual(result.total_ok, 1)
        self.assertEqual(result.total_acao, 1)
        self.assertEqual(result.total_mensagens, 1)
        self.assertEqual(result.grupos[0].nome_conta, "CONTA 2")

    def test_grouping_same_account_same_status_same_date(self):
        # Mesmo grupo com mesma data: junta em 1 única mensagem
        data = [
            {
                "Nome da Conta": "CONTA X",
                "Empresa": "Empresa A",
                "CNPJ": "11.111.111/0001-11",
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            },
            {
                "Nome da Conta": "CONTA X",
                "Empresa": "Empresa B",
                "CNPJ": "22.222.222/0001-22",
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            }
        ]
        df = pd.DataFrame(data)
        result = process_dataframe(df, self.templates)

        self.assertEqual(result.total_mensagens, 1)
        grupo = result.grupos[0]
        self.assertEqual(len(grupo.itens), 2)
        self.assertEqual(grupo.data_expiracao, "17/09/2026")
        self.assertFalse(grupo.tem_datas_diferentes)

        msg = build_single_message(grupo, self.templates)
        bloco_a = "Cliente: Empresa A\nCNPJ: 11.111.111/0001-11\nVencimento: 17/09/2026"
        bloco_b = "Cliente: Empresa B\nCNPJ: 22.222.222/0001-22\nVencimento: 17/09/2026"
        self.assertIn(f"{bloco_a}\n\n{bloco_b}", msg)

    def test_multi_status_unified_message(self):
        # Valida unificação de múltiplos status do mesmo cliente em 1 única mensagem
        data = [
            {
                "Nome da Conta": "CONTA X",
                "Empresa": "Empresa A",
                "CNPJ": "11.111.111/0001-11",
                "Certificado Expira em": "07/10/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            },
            {
                "Nome da Conta": "CONTA X",
                "Empresa": "Empresa B",
                "CNPJ": "22.222.222/0001-22",
                "Certificado Expira em": "12/10/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            },
            {
                "Nome da Conta": "CONTA X",
                "Empresa": "Empresa C",
                "CNPJ": "33.333.333/0001-33",
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "CERTIFICADO EXPIRA EM 30 DIAS"
            }
        ]
        df = pd.DataFrame(data)
        result = process_dataframe(df, self.templates)

        # Deve ser gerada 1 única mensagem para a CONTA X com todos os status
        self.assertEqual(result.total_mensagens, 1)

        grupo = result.grupos[0]
        self.assertEqual(grupo.nome_conta, "CONTA X")
        self.assertTrue(grupo.is_multi_status)
        self.assertEqual(len(grupo.itens), 3)
        self.assertEqual(len(grupo.sub_groups), 2)

        msg = build_single_message(grupo, self.templates)

        # Deve conter seções para ambos os status
        self.assertIn("ENTRAR EM CONTATO, EXPIRA EM 5 DIAS", msg)
        self.assertIn("CERTIFICADO EXPIRA EM 30 DIAS", msg)
        self.assertIn("Cliente: Empresa A\nCNPJ: 11.111.111/0001-11\nVencimento: 07/10/2026", msg)
        self.assertIn("Cliente: Empresa B\nCNPJ: 22.222.222/0001-22\nVencimento: 12/10/2026", msg)
        self.assertIn("Cliente: Empresa C\nCNPJ: 33.333.333/0001-33\nVencimento: 17/09/2026", msg)

    def test_single_status_different_dates(self):
        # Valida grupo de status único mas com datas de vencimento diferentes
        data = [
            {
                "Nome da Conta": "CONTA Y",
                "Empresa": "Empresa 1",
                "CNPJ": "11.111.111/0001-11",
                "Certificado Expira em": "07/10/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            },
            {
                "Nome da Conta": "CONTA Y",
                "Empresa": "Empresa 2",
                "CNPJ": "22.222.222/0001-22",
                "Certificado Expira em": "12/10/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            }
        ]
        df = pd.DataFrame(data)
        result = process_dataframe(df, self.templates)

        self.assertEqual(result.total_mensagens, 1)
        grupo = result.grupos[0]
        self.assertFalse(grupo.is_multi_status)
        self.assertTrue(grupo.tem_datas_diferentes)

        msg = build_single_message(grupo, self.templates)
        bloco_1 = "Cliente: Empresa 1\nCNPJ: 11.111.111/0001-11\nVencimento: 07/10/2026"
        bloco_2 = "Cliente: Empresa 2\nCNPJ: 22.222.222/0001-22\nVencimento: 12/10/2026"
        self.assertIn(f"{bloco_1}\n\n{bloco_2}", msg)

    def test_single_item_conceptual_example(self):
        # Valida exemplo conceitual de 1 registro
        data = [
            {
                "Nome da Conta": "CONTA TESTE",
                "Empresa": "EMPRESA TESTE LTDA",
                "CNPJ": "00000000000100",
                "Certificado Expira em": "07/10/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            }
        ]
        df = pd.DataFrame(data)
        result = process_dataframe(df, self.templates)

        self.assertEqual(result.total_mensagens, 1)
        grupo = result.grupos[0]
        msg = build_single_message(grupo, self.templates)

        self.assertIn("EMPRESA TESTE LTDA", msg)
        self.assertIn("00.000.000/0001-00", msg)
        self.assertIn("07/10/2026", msg)

    def test_legacy_template_placeholder_compatibility(self):
        # Valida retrocompatibilidade caso um template personalizado use {clientes_cnpjs}
        templates_custom = {
            "STATUS LEGADO": {
                "template": "Alerta!\n\n{clientes_cnpjs}\n\nFim."
            }
        }
        data = [
            {
                "Nome da Conta": "CONTA LEGADA",
                "Empresa": "Empresa Legada LTDA",
                "CNPJ": "11.222.333/0001-44",
                "Certificado Expira em": "07/10/2026",
                "status do fluxo": "STATUS LEGADO"
            }
        ]
        df = pd.DataFrame(data)
        result = process_dataframe(df, templates_custom)
        msg = build_single_message(result.grupos[0], templates_custom)
        self.assertIn("Cliente: Empresa Legada LTDA\nCNPJ: 11.222.333/0001-44", msg)

    def test_unknown_status_detected(self):
        data = [
            {
                "Nome da Conta": "CONTA Y",
                "Empresa": "Empresa Y",
                "CNPJ": "44.444.444/0001-44",
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "STATUS NOVO DESCONHECIDO"
            }
        ]
        df = pd.DataFrame(data)
        result = process_dataframe(df, self.templates)

        self.assertIn("STATUS NOVO DESCONHECIDO", result.status_desconhecidos)
        self.assertFalse(result.grupos[0].status_configurado)

    def test_problematic_incomplete_record(self):
        data = [
            {
                "Nome da Conta": "CONTA Z",
                "Empresa": "",  # Vazio
                "CNPJ": "55.555.555/0001-55",
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            },
            {
                "Nome da Conta": "CONTA Z",
                "Empresa": "Empresa Z2",
                "CNPJ": "",  # Vazio
                "Certificado Expira em": "17/09/2026",
                "status do fluxo": "ENTRAR EM CONTATO, EXPIRA EM 5 DIAS"
            }
        ]
        df = pd.DataFrame(data)
        result = process_dataframe(df, self.templates)

        self.assertEqual(len(result.registros_problematicos), 2)
        # Nenhuma mensagem incompleta gerada
        self.assertEqual(result.total_mensagens, 0)


if __name__ == "__main__":
    unittest.main()
