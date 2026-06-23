"""
Testes do matching CT2 (razao) x SFT (livro fiscal).

Cobre os 3 fases descritas na docstring de match_ct2_sft, incluindo os casos
reais descobertos ao validar a conciliacao de impostos da Rancheiro (conta
COFINS A RECUPERAR, marco/2026): NF/CT-e repetida entre fornecedores
diferentes, NF dividida em varios itens no SFT, desambiguacao por data e
candidatas de valor zero.

Uso:
    python -m unittest tools.fiscal.test_match_ct2_sft -v
"""
import unittest

from tools.fiscal.match_ct2_sft import match_ct2_sft


class Fase1MatchExato(unittest.TestCase):
    def test_1_para_1_com_ct2_key_valida(self):
        ct2 = [{"ct2_key": "0119000000061001014921", "debito": 152.65}]
        sft = [{"filial": "0119", "nf": "000000061", "cliefor": "014921", "valcont": 152.65}]
        ct2_res, sft_res = match_ct2_sft(ct2, sft)
        self.assertTrue(ct2_res[0]["matched"])
        self.assertTrue(sft_res[0]["matched"])

    def test_sem_correspondencia_fica_como_diferenca(self):
        ct2 = [{"ct2_key": "0119000000061001014921", "debito": 999.99}]
        sft = [{"filial": "0119", "nf": "000000061", "cliefor": "014921", "valcont": 152.65}]
        ct2_res, sft_res = match_ct2_sft(ct2, sft)
        self.assertFalse(ct2_res[0]["matched"])
        self.assertFalse(sft_res[0]["matched"])

    def test_valor_zero_no_ct2_e_descartado_sem_comparar(self):
        ct2 = [{"ct2_key": "", "debito": 0}]
        sft: list = []
        ct2_res, _ = match_ct2_sft(ct2, sft)
        self.assertTrue(ct2_res[0]["matched"])  # nunca aparece como diferenca


class Fase2ReconciliacaoPorNota(unittest.TestCase):
    def test_soma_do_grupo_cobre_nota_dividida_em_itens(self):
        chave = "0119000000061001014921"
        ct2 = [{"ct2_key": chave, "debito": 18.72}]
        sft = [
            {"filial": "0119", "nf": "000000061", "cliefor": "014921", "valcont": 6.79},
            {"filial": "0119", "nf": "000000061", "cliefor": "014921", "valcont": 7.16},
            {"filial": "0119", "nf": "000000061", "cliefor": "014921", "valcont": 4.77},
        ]
        ct2_res, sft_res = match_ct2_sft(ct2, sft)
        self.assertTrue(ct2_res[0]["matched"])
        self.assertTrue(all(r["matched"] for r in sft_res))

    def test_greedy_cobre_lancamento_extra_sem_zerar_o_resto(self):
        chave = "0119000000061001014921"
        # CT2 lanca a nota principal + um complemento sem par no SFT.
        ct2 = [
            {"ct2_key": chave, "debito": 100.00},
            {"ct2_key": chave, "debito": 5.00},
        ]
        sft = [
            {"filial": "0119", "nf": "000000061", "cliefor": "014921", "valcont": 100.00},
        ]
        ct2_res, sft_res = match_ct2_sft(ct2, sft)
        self.assertTrue(ct2_res[0]["matched"])
        self.assertFalse(ct2_res[1]["matched"])  # complemento sem par fica como diferenca
        self.assertTrue(sft_res[0]["matched"])


class Fase3FallbackPorHistorico(unittest.TestCase):
    def test_nf_extraida_do_historico_casa_1_para_1(self):
        ct2 = [{"historico": "PIS CREDITADO NFE 61", "debito": 152.65, "ct2_key": ""}]
        sft = [{"filial": "0119", "nf": "000000061", "cliefor": "014921", "valpis": 152.65}]
        ct2_res, sft_res = match_ct2_sft(ct2, sft, campo_valor_sft="valpis", campo_valor_ct2="debito")
        self.assertTrue(ct2_res[0]["matched"])
        self.assertTrue(sft_res[0]["matched"])

    def test_cte_no_historico_tambem_e_reconhecido(self):
        ct2 = [{"historico": "COFINS AQUISICAO FRETE CTE 124", "debito": 18.72, "ct2_key": ""}]
        sft = [{"filial": "0119", "nf": "000000124", "cliefor": "001876", "valcof": 18.72, "especie": "CTE"}]
        ct2_res, sft_res = match_ct2_sft(ct2, sft, campo_valor_sft="valcof", campo_valor_ct2="debito")
        self.assertTrue(ct2_res[0]["matched"])
        self.assertTrue(sft_res[0]["matched"])

    def test_nf_dividida_em_itens_sem_chave(self):
        ct2 = [{"historico": "PIS CREDITADO NFE 172277", "debito": 18.72, "ct2_key": ""}]
        sft = [
            {"filial": "0119", "nf": "000172277", "cliefor": "001876", "valpis": 6.79},
            {"filial": "0119", "nf": "000172277", "cliefor": "001876", "valpis": 7.16},
            {"filial": "0119", "nf": "000172277", "cliefor": "001876", "valpis": 4.77},
        ]
        ct2_res, sft_res = match_ct2_sft(ct2, sft, campo_valor_sft="valpis", campo_valor_ct2="debito")
        self.assertTrue(ct2_res[0]["matched"])
        self.assertTrue(all(r["matched"] for r in sft_res))

    def test_nf_ambigua_entre_fornecedores_sem_data_nao_casa(self):
        ct2 = [{"historico": "PIS CREDITADO NFE 61", "debito": 152.65, "ct2_key": ""}]
        sft = [
            {"filial": "0119", "nf": "000000061", "cliefor": "014921", "valpis": 152.65},
            {"filial": "0220", "nf": "000000061", "cliefor": "099999", "valpis": 152.65},
        ]
        ct2_res, sft_res = match_ct2_sft(ct2, sft, campo_valor_sft="valpis", campo_valor_ct2="debito")
        self.assertFalse(ct2_res[0]["matched"])
        self.assertFalse(any(r["matched"] for r in sft_res))

    def test_filial_no_ct2_usa_chave_mais_forte(self):
        ct2 = [{"historico": "PIS CREDITADO NFE 61", "debito": 152.65, "ct2_key": "", "filial": "0119"}]
        sft = [
            {"filial": "0119", "nf": "000000061", "cliefor": "014921", "valpis": 152.65},
            {"filial": "0220", "nf": "000000061", "cliefor": "099999", "valpis": 152.65},
        ]
        ct2_res, sft_res = match_ct2_sft(ct2, sft, campo_valor_sft="valpis", campo_valor_ct2="debito")
        self.assertTrue(ct2_res[0]["matched"])
        self.assertTrue(sft_res[0]["matched"])  # filial 0119
        self.assertFalse(sft_res[1]["matched"])  # filial 0220, nunca disputa

    def test_filial_diferente_da_unica_candidata_nao_casa(self):
        ct2 = [{"historico": "PIS CREDITADO NFE 61", "debito": 152.65, "ct2_key": "", "filial": "0220"}]
        sft = [{"filial": "0119", "nf": "000000061", "cliefor": "014921", "valpis": 152.65}]
        ct2_res, sft_res = match_ct2_sft(ct2, sft, campo_valor_sft="valpis", campo_valor_ct2="debito")
        self.assertFalse(ct2_res[0]["matched"])
        self.assertFalse(sft_res[0]["matched"])

    def test_ambiguo_desambiguado_pela_data(self):
        # Caso real: CT-e 209, mesmo fornecedor em duas filiais/datas distintas.
        ct2 = [{"historico": "COFINS AQUISICAO FRETE CTE 209", "debito": 823.31, "ct2_key": "", "data": "18/03/2026"}]
        sft = [
            {"filial": "0123", "nf": "000000209", "cliefor": "014921", "valcof": 823.31, "entrada": "18/03/2026"},
            {"filial": "0101", "nf": "000000209", "cliefor": "014921", "valcof": 346.35, "entrada": "19/03/2026"},
        ]
        ct2_res, sft_res = match_ct2_sft(ct2, sft, campo_valor_sft="valcof", campo_valor_ct2="debito")
        self.assertTrue(ct2_res[0]["matched"])
        self.assertTrue(sft_res[0]["matched"])  # entrada 18/03 -- bate com a data do razao
        self.assertFalse(sft_res[1]["matched"])  # entrada 19/03 -- nao bate

    def test_ambiguo_mesmo_com_data_nao_casa(self):
        # Dois fornecedores diferentes, mesma NF, mesma data -- a data sozinha
        # nao resolve, tem que continuar como diferenca.
        ct2 = [{"historico": "PIS CREDITADO NFE 61", "debito": 152.65, "ct2_key": "", "data": "18/03/2026"}]
        sft = [
            {"filial": "0119", "nf": "000000061", "cliefor": "014921", "valpis": 152.65, "entrada": "18/03/2026"},
            {"filial": "0101", "nf": "000000061", "cliefor": "099999", "valpis": 152.65, "entrada": "18/03/2026"},
        ]
        ct2_res, sft_res = match_ct2_sft(ct2, sft, campo_valor_sft="valpis", campo_valor_ct2="debito")
        self.assertFalse(ct2_res[0]["matched"])
        self.assertFalse(any(r["matched"] for r in sft_res))

    def test_nf_repetida_entre_varias_faturas_resolve_por_data_e_fornecedor(self):
        # Caso real: NF "61" reaparece em 4 lancamentos do razao (3 fornecedores
        # diferentes, datas diferentes) -- cada lancamento so' deve disputar
        # contra as notas do SFT do MESMO dia.
        ct2 = [
            {"historico": "COFINS CREDITADO NFE 61", "debito": 703.13, "ct2_key": "", "data": "02/03/2026"},
            {"historico": "COFINS CREDITADO NFE 61", "debito": 36.41, "ct2_key": "", "data": "19/03/2026"},
            {"historico": "COFINS CREDITADO NFE 61", "debito": 1.33, "ct2_key": "", "data": "19/03/2026"},
            {"historico": "COFINS CREDITADO NFE 61", "debito": 49.10, "ct2_key": "", "data": "24/03/2026"},
        ]
        sft = [
            {"filial": "0117", "nf": "000000061", "cliefor": "009094", "valcof": 36.41, "entrada": "19/03/2026"},
            {"filial": "0117", "nf": "000000061", "cliefor": "009094", "valcof": 1.33, "entrada": "19/03/2026"},
            {"filial": "0117", "nf": "000000061", "cliefor": "008280", "valcof": 8.55, "entrada": "24/03/2026"},
            {"filial": "0117", "nf": "000000061", "cliefor": "008280", "valcof": 40.55, "entrada": "24/03/2026"},
            {"filial": "0119", "nf": "000000061", "cliefor": "014921", "valcof": 703.13, "entrada": "02/03/2026"},
        ]
        ct2_res, sft_res = match_ct2_sft(ct2, sft, campo_valor_sft="valcof", campo_valor_ct2="debito")
        self.assertTrue(all(r["matched"] for r in ct2_res))
        self.assertTrue(all(r["matched"] for r in sft_res))

    def test_candidata_de_valor_zero_nao_conta_para_ambiguidade(self):
        # Caso real: NF 208, mesmo dia, dois fornecedores -- um deles com
        # valor zero (ruido) nao pode bloquear o match do fornecedor certo.
        ct2 = [{"historico": "COFINS CREDITADO NFE 208", "debito": 254.45, "ct2_key": "", "data": "10/03/2026"}]
        sft = [
            {"filial": "0101", "nf": "000000208", "cliefor": "008313", "valcof": 0, "entrada": "10/03/2026"},
            {"filial": "0119", "nf": "000000208", "cliefor": "029948", "valcof": 254.45, "entrada": "10/03/2026"},
        ]
        ct2_res, sft_res = match_ct2_sft(ct2, sft, campo_valor_sft="valcof", campo_valor_ct2="debito")
        self.assertTrue(ct2_res[0]["matched"])
        self.assertFalse(sft_res[0]["matched"])  # valor zero, nunca casa
        self.assertTrue(sft_res[1]["matched"])

    def test_sem_padrao_nf_ou_cte_no_historico_fica_como_diferenca(self):
        ct2 = [{"historico": "AJUSTE MANUAL DE SALDO", "debito": 100.00, "ct2_key": ""}]
        sft = [{"filial": "0119", "nf": "000000061", "cliefor": "014921", "valcont": 100.00}]
        ct2_res, sft_res = match_ct2_sft(ct2, sft)
        self.assertFalse(ct2_res[0]["matched"])
        self.assertFalse(sft_res[0]["matched"])


if __name__ == "__main__":
    unittest.main()
