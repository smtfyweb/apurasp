import duckdb, json, pathlib, collections, csv

con = duckdb.connect("data/apurasp.duckdb", read_only=True)
Q = lambda sql: con.execute(sql).fetchall()
OUT = pathlib.Path("public/data/municipios")
ibge = {int(t): str(i) for t, i in Q("""SELECT CD_MUNICIPIO_TSE, CD_MUNICIPIO_IBGE
    FROM read_parquet('data/parquet/municipio_tse_ibge/municipio_tse_ibge.parquet') WHERE SG_UF='SP'""")}

print("=== Capital x Portal do Holanda (federal 2026) ===")
for r in Q("""SELECT NM_URNA_CANDIDATO, SG_PARTIDO, sum(CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT))
    FROM v_votos_cand WHERE ano=2026 AND upper(DS_CARGO)='DEPUTADO FEDERAL' AND NR_TURNO='1'
      AND upper(NM_MUNICIPIO) IN ('SÃO PAULO','SAO PAULO') GROUP BY 1,2 ORDER BY 3 DESC LIMIT 5"""):
    print(r)
print("Esperado: Pavanato 785870 | Erika 618361 | Tabata 238734 | Sâmia 217662 | Luna 182643")

dados = collections.defaultdict(dict)
for ano in (2022, 2026):
    for cargo, chave in (("DEPUTADO FEDERAL", "federal"), ("DEPUTADO ESTADUAL", "estadual")):
        tot = dict(Q(f"""SELECT CAST(CD_MUNICIPIO AS INT), sum(CAST(QT_TOTAL_VOTOS_VALIDOS AS BIGINT)) FROM v_detalhe
                         WHERE ano={ano} AND upper(DS_CARGO)='{cargo}' AND NR_TURNO='1' GROUP BY 1"""))
        cand, part = collections.defaultdict(list), collections.defaultdict(lambda: collections.Counter())
        for c, nome, p, sit, v in Q(f"""SELECT CAST(CD_MUNICIPIO AS INT), any_value(NM_URNA_CANDIDATO), any_value(SG_PARTIDO),
                any_value(DS_SIT_TOT_TURNO), sum(CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT)) FROM v_votos_cand
                WHERE ano={ano} AND upper(DS_CARGO)='{cargo}' AND NR_TURNO='1' GROUP BY CD_MUNICIPIO, SQ_CANDIDATO"""):
            cand[c].append((nome, p, (sit or "").upper().startswith("ELEITO"), v or 0))
            part[c][p] += v or 0
        for c, p, v in Q(f"""SELECT CAST(CD_MUNICIPIO AS INT), SG_PARTIDO, sum(CAST(QT_VOTOS_LEGENDA_VALIDOS AS BIGINT))
                FROM v_votos_partido WHERE ano={ano} AND upper(DS_CARGO)='{cargo}' AND NR_TURNO='1' GROUP BY 1,2"""):
            part[c][p] += v or 0
        for c, lst in cand.items():
            t = tot.get(c) or 0
            pct = lambda v: round(100 * v / t, 2) if t else None
            dados[c].setdefault(str(ano), {})[chave] = {
                "votos_validos": t,
                "candidatos": [{"nome": n, "partido": p, "eleito_no_estado": e, "votos": v, "pct": pct(v)}
                               for n, p, e, v in sorted(lst, key=lambda x: -x[3])[:10]],
                "partidos": [{"partido": p, "votos": v, "pct": pct(v)} for p, v in part[c].most_common(10)]}

n = 0
for c, d in dados.items():
    f = OUT / f"{ibge.get(c, '')}.json"
    if f.exists():
        j = json.load(open(f, encoding="utf-8")); j["deputados"] = d
        f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8"); n += 1
print(f"\n{n} municípios atualizados com deputados 2022 e 2026")

esp = pathlib.Path("data/referencias/espectro_partidos.csv")
if esp.exists() and esp.stat().st_size > 0:
    print("espectro_partidos.csv já existe, mantido.")
else:
    rows = Q("""SELECT SG_PARTIDO, any_value(NM_PARTIDO) FROM v_cand WHERE ano=2026 AND SG_PARTIDO IS NOT NULL GROUP BY 1 ORDER BY 1""")
    with open(esp, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["sigla", "nome", "espectro", "criterio_fonte"])
        for s, nm in rows: w.writerow([s, nm, "", ""])
    print(f"espectro_partidos.csv criado com {len(rows)} partidos para classificar")

for ibge_cod in ("3534401", "3505708"):
    j = json.load(open(OUT / f"{ibge_cod}.json", encoding="utf-8"))
    print("\n", j["nome"], "- partidos mais votados p/ estadual 2026:",
          [(x["partido"], x["pct"]) for x in j["deputados"]["2026"]["estadual"]["partidos"][:5]])
