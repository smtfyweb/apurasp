import duckdb, glob, os
con = duckdb.connect("data/apurasp.duckdb", read_only=True)
def q(t, sql):
    print(f"\n=== {t} ===")
    try:
        r = con.execute(sql)
        print([d[0] for d in r.description])
        for row in r.fetchall(): print(row)
    except Exception as e: print("ERRO:", str(e)[:300])

print("Parquets de votação por seção:", [os.path.basename(f) for f in glob.glob("data/parquet/votacao_secao/*.parquet")])
q("Locais de votação: coordenadas (Osasco e Barueri)", """
 SELECT ano, NM_MUNICIPIO, count(DISTINCT NR_ZONA||'-'||NR_LOCAL_VOTACAO) locais, count(DISTINCT NR_ZONA||'-'||NR_SECAO) secoes,
        count(*) FILTER (WHERE TRY_CAST(replace(NR_LATITUDE, ',', '.') AS DOUBLE) BETWEEN -26 AND -19) com_coord
 FROM v_locais WHERE upper(NM_MUNICIPIO) IN ('OSASCO','BARUERI') GROUP BY ALL ORDER BY 2,1""")
q("Amostra de locais (Barueri 2026)", """
 SELECT NM_LOCAL_VOTACAO, NM_BAIRRO, NR_LATITUDE, NR_LONGITUDE, QT_ELEITOR_SECAO FROM v_locais
 WHERE ano=2026 AND upper(NM_MUNICIPIO)='BARUERI' LIMIT 5""")
q("Eleitores por local de votação, Barueri 2024 (tamanho da unidade)", """
 WITH l AS (SELECT NR_ZONA, NR_LOCAL_VOTACAO, sum(TRY_CAST(QT_ELEITOR_SECAO AS BIGINT)) e, count(*) secoes FROM v_locais
            WHERE ano=2024 AND upper(NM_MUNICIPIO)='BARUERI' GROUP BY 1,2)
 SELECT count(*) locais, min(e), median(e), max(e), median(secoes), max(secoes) FROM l""")
q("Cobertura da chave zona+seção entre as três bases (Barueri 2024)", """
 WITH v AS (SELECT DISTINCT NR_ZONA, NR_SECAO FROM v_votos_secao WHERE ano=2024 AND upper(NM_MUNICIPIO)='BARUERI'),
      l AS (SELECT DISTINCT NR_ZONA, NR_SECAO FROM v_locais WHERE ano=2024 AND upper(NM_MUNICIPIO)='BARUERI'),
      p AS (SELECT DISTINCT NR_ZONA, NR_SECAO FROM v_perfil_secao WHERE ano=2024 AND upper(NM_MUNICIPIO)='BARUERI')
 SELECT (SELECT count(*) FROM v) votos, (SELECT count(*) FROM l) locais, (SELECT count(*) FROM p) perfil,
        (SELECT count(*) FROM v JOIN l USING (NR_ZONA, NR_SECAO)) votos_x_locais,
        (SELECT count(*) FROM v JOIN p USING (NR_ZONA, NR_SECAO)) votos_x_perfil""")
q("Vereador mais votado de Barueri em 2024: onde ele foi forte (por local de votação)", """
 WITH base AS (SELECT NR_ZONA, NR_LOCAL_VOTACAO, NM_LOCAL_VOTACAO, NR_VOTAVEL, NM_VOTAVEL, TRY_CAST(SQ_CANDIDATO AS BIGINT) sq, CAST(QT_VOTOS AS BIGINT) qt
               FROM v_votos_secao WHERE ano=2024 AND upper(NM_MUNICIPIO)='BARUERI' AND upper(DS_CARGO)='VEREADOR' AND NR_TURNO='1'),
      top AS (SELECT sq, any_value(NM_VOTAVEL) nome FROM base WHERE sq > 0 GROUP BY 1 ORDER BY sum(qt) DESC LIMIT 1)
 SELECT (SELECT nome FROM top) candidato, NR_ZONA zona, NR_LOCAL_VOTACAO, any_value(NM_LOCAL_VOTACAO) local,
        sum(qt) FILTER (WHERE sq = (SELECT sq FROM top)) votos_candidato,
        sum(qt) FILTER (WHERE NR_VOTAVEL NOT IN ('95','96')) votos_validos_aprox
 FROM base GROUP BY 2,3 ORDER BY votos_candidato DESC NULLS LAST LIMIT 6""")
