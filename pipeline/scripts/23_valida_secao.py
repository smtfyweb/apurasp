import duckdb
con = duckdb.connect("data/apurasp.duckdb", read_only=True)
print("anos com votos por seção no banco:", sorted(r[0] for r in con.execute("SELECT DISTINCT ano FROM v_votos_secao").fetchall()))
MUN = ("SELECT TRY_CAST(CD_MUNICIPIO_TSE AS INT) FROM read_parquet('data/parquet/municipio_tse_ibge/municipio_tse_ibge.parquet') "
       "WHERE SG_UF='SP' AND upper(NM_MUNICIPIO_TSE) IN ('BARUERI','OSASCO')")
CG = "('DEPUTADO FEDERAL','DEPUTADO ESTADUAL')"
sql = f"""WITH z AS (SELECT ano, TRY_CAST(CD_MUNICIPIO AS INT) m, upper(DS_CARGO) cg, TRY_CAST(SQ_CANDIDATO AS BIGINT) sq, NR_ZONA zona,
        max(NM_URNA_CANDIDATO) nome, max(COALESCE(TRY_CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT), 0)) v
      FROM v_votos_cand WHERE ano IN (2022, 2026) AND NR_TURNO='1' AND upper(DS_CARGO) IN {CG} AND TRY_CAST(CD_MUNICIPIO AS INT) IN ({MUN})
      GROUP BY ALL),
   cs AS (SELECT ano, m, cg, sq, any_value(nome) nome, sum(v) v FROM z GROUP BY ALL),
   topo AS (SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY ano, m, cg ORDER BY v DESC) rk FROM cs) WHERE rk <= 2),
   s AS (SELECT ano, TRY_CAST(CD_MUNICIPIO AS INT) m, upper(DS_CARGO) cg, TRY_CAST(SQ_CANDIDATO AS BIGINT) sq, sum(TRY_CAST(QT_VOTOS AS BIGINT)) v
      FROM v_votos_secao WHERE ano IN (2022, 2026) AND NR_TURNO='1' AND upper(DS_CARGO) IN {CG} AND TRY_CAST(CD_MUNICIPIO AS INT) IN ({MUN})
      GROUP BY ALL)
 SELECT topo.ano, topo.cg, topo.nome, topo.v AS por_zona, s.v AS por_secao, s.v - topo.v AS diferenca
 FROM topo LEFT JOIN s ON s.ano = topo.ano AND s.m = topo.m AND s.cg = topo.cg AND s.sq = topo.sq
 ORDER BY topo.ano, topo.m, topo.cg, topo.v DESC"""
r = con.execute(sql)
print("\nValidação (por_zona = total oficial do município; por_secao = soma das seções; diferença esperada = 0)")
print([d[0] for d in r.description])
for row in r.fetchall(): print(row)
