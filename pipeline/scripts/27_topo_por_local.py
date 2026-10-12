import duckdb, json, pathlib, collections

TOPN = 8
CARGOS = {2024: ["VEREADOR", "PREFEITO"], 2022: ["DEPUTADO FEDERAL", "DEPUTADO ESTADUAL"], 2026: ["DEPUTADO FEDERAL", "DEPUTADO ESTADUAL"]}
CHAVE = {"VEREADOR": "vereador", "PREFEITO": "prefeito", "DEPUTADO FEDERAL": "federal", "DEPUTADO ESTADUAL": "estadual"}
con = duckdb.connect("data/apurasp.duckdb", read_only=True)
Q = lambda sql, *a: con.execute(sql, list(a)).fetchall()
OUT = pathlib.Path("public/data/topo"); OUT.mkdir(parents=True, exist_ok=True)
ibge = {int(t): str(i) for t, i in Q("""SELECT CD_MUNICIPIO_TSE, CD_MUNICIPIO_IBGE
    FROM read_parquet('data/parquet/municipio_tse_ibge/municipio_tse_ibge.parquet') WHERE SG_UF='SP'""")}
info = {(a, sq): (n, p) for a, sq, n, p in Q("SELECT ano, TRY_CAST(SQ_CANDIDATO AS BIGINT), any_value(NM_URNA_CANDIDATO), any_value(SG_PARTIDO) FROM v_cand GROUP BY 1, 2")}
tem = {r[0] for r in Q("SELECT DISTINCT ano FROM v_votos_secao")}
T = collections.defaultdict(lambda: collections.defaultdict(dict))
for ano, cargos in CARGOS.items():
    if ano not in tem: print("sem votos por seção em", ano); continue
    for cargo in cargos:
        for turno in ("1", "2"):
            rows = Q("""WITH b AS (
                  SELECT TRY_CAST(CD_MUNICIPIO AS INT) m, TRY_CAST(NR_ZONA AS INT) z, TRY_CAST(NR_LOCAL_VOTACAO AS INT) l,
                         TRY_CAST(SQ_CANDIDATO AS BIGINT) sq, any_value(NM_VOTAVEL) nome, sum(COALESCE(TRY_CAST(QT_VOTOS AS BIGINT), 0)) v
                  FROM v_votos_secao WHERE ano = ? AND upper(DS_CARGO) = ? AND NR_TURNO = ? AND TRY_CAST(SQ_CANDIDATO AS BIGINT) > 0
                  GROUP BY 1, 2, 3, 4),
                r AS (SELECT *, row_number() OVER (PARTITION BY m, z, l ORDER BY v DESC, sq) rk FROM b WHERE v > 0)
                SELECT m, z, l, sq, nome, v FROM r WHERE rk <= ? ORDER BY m, z, l, rk""", ano, cargo, turno, TOPN)
            if not rows: continue
            por = collections.defaultdict(lambda: {"idx": {}, "c": [], "l": {}})
            for m, z, l, sq, nome, v in rows:
                if m not in ibge: continue
                d = por[m]
                if sq not in d["idx"]:
                    nm, sg = info.get((ano, sq), (None, None))
                    d["idx"][sq] = len(d["c"]); d["c"].append([nm or nome, sg or ""])
                d["l"].setdefault(f"{z}-{l}", []).append([d["idx"][sq], v])
            for m, d in por.items(): T[m][str(ano)][f"{CHAVE[cargo]}{turno}"] = {"c": d["c"], "l": d["l"]}
            print(f"   {ano} {CHAVE[cargo]} turno {turno}: {len(por)} municípios")
tam = 0
for m, d in T.items():
    p = OUT / f"{ibge[m]}.json"
    p.write_text(json.dumps({"ibge": ibge[m], "t": d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"); tam += p.stat().st_size
print(f"topo: {len(T)} municípios | {tam / 1e6:.1f} MB")
