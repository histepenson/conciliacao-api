import psycopg2

for label, url in [
    ("shinkansen (staging)", "postgresql://postgres:TEQdHCNkUipWQKsbesMbkvzPvPYfArkd@shinkansen.proxy.rlwy.net:54745/railway?sslmode=require"),
    ("turntable (develop)", "postgresql://postgres:mMXKWaoRkRRpHxlVszpEPdenEWqJhKSL@turntable.proxy.rlwy.net:48244/railway?sslmode=require"),
]:
    print(f"\n{'='*60}")
    print(f"DB: {label}")
    print(f"{'='*60}")
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("""
            SELECT pc.id, pc.tipo_relatorio, pc.status, pc.total_registros,
                   COUNT(pr.id) AS reais_no_banco, pc.data_base
            FROM concilia.protheus_carga pc
            LEFT JOIN concilia.protheus_carga_registro pr ON pr.carga_id = pc.id
            GROUP BY pc.id, pc.tipo_relatorio, pc.status, pc.total_registros, pc.data_base
            ORDER BY pc.id DESC
            LIMIT 15
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        print(" | ".join(cols))
        print("-" * 80)
        for r in rows:
            print(" | ".join(str(x) for x in r))
        conn.close()
    except Exception as e:
        print(f"Erro: {e}")
