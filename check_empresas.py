from db import SessionLocal
from models.empresa import Empresa
from models.produto import Produto
from models.estoque import EstoqueSaldo

db = SessionLocal()
empresas = db.query(Empresa).all()
print("=== EMPRESAS ===")
for e in empresas:
    print(f"  id={e.id}, nome={e.nome}, status={e.status}")

prods = db.query(Produto).all()
print(f"\nProdutos no banco: {len(prods)}")
if prods:
    empresa_ids = set(p.empresa_id for p in prods)
    print(f"empresa_ids nos produtos: {empresa_ids}")

saldos = db.query(EstoqueSaldo).all()
print(f"\nSaldos no banco: {len(saldos)}")
if saldos:
    empresa_ids_s = set(s.empresa_id for s in saldos)
    print(f"empresa_ids nos saldos: {empresa_ids_s}")
db.close()
