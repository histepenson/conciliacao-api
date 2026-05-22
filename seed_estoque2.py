"""
Seed estoque para empresa_id=2 (DIAMANTE ALIMENTOS).
Importa e re-executa o seed_estoque com empresa diferente.
"""
import importlib, sys

# Patch EMPRESA_ID antes de executar o seed original
import seed_estoque as _s

# Salva originais
_orig_eid = _s.EMPRESA_ID
_orig_cnpj = _s.CNPJ_EMPRESA

# Override para empresa 2
_s.EMPRESA_ID = 2
_s.CNPJ_EMPRESA = "00000000000002"  # CNPJ ficticio para empresa 2

# Re-executa a funcao principal
if hasattr(_s, 'main'):
    _s.main()
else:
    # Seed nao tem funcao main - re-executa o modulo diretamente
    exec(open("seed_estoque.py").read().replace("EMPRESA_ID = 1", "EMPRESA_ID = 2").replace(
        'CNPJ_EMPRESA = "23828180000108"', 'CNPJ_EMPRESA = "00000000000002"'
    ))
