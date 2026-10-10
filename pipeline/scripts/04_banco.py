import duckdb

con = duckdb.connect("data/apurasp.duckdb")
P = "data/parquet"
VIEWS = {
 "v_cand":          "consulta_cand/consulta_cand_*_SP.parquet",
 "v_vagas":         "consulta_vagas/consulta_vagas_*_SP.parquet",
 "v_perfil_mun":    "perfil_eleitorado/perfil_eleitorado_*_SP.parquet",
 "v_perfil_secao":  "perfil_eleitor_secao/perfil_eleitor_secao_*_SP.parquet",
 "v_locais":        "eleitorado_locais_votacao/eleitorado_local_votacao_*.parquet",
 "v_votos_secao":   "votacao_secao/votacao_secao_*_SP.parquet",
 "v_votos_cand":    "votacao_candidato_munzona/votacao_candidato_munzona_*.parquet",
 "v_votos_partido": "votacao_partido_munzona/votacao_partido_munzona_*.parquet",
 "v_detalhe":       "detalhe_votacao_munzona/detalhe_votacao_munzona_*.parquet",
}
for nome, padrao in VIEWS.items():
    try:
        con.execute(f"""CREATE OR REPLACE VIEW {nome} AS
          SELECT *, CAST(regexp_extract(filename, '(20[0-9][0-9])', 1) AS INT) AS ano
          FROM read_parquet('{P}/{padrao}', union_by_name=true, filename=true)""")
        print(f"view {nome:16} ok")
    except Exception as e:
        print(f"view {nome:16} ERRO: {str(e)[:150]}")

def q(titulo, sql):
    print(f"\n=== {titulo} ===")
    try:
        r = con.execute(sql)
        print([d[0] for d in r.description])
        for row in r.fetchall(): print(row)
    except Exception as e:
        print("ERRO:", str(e)[:300])

q("Colunas de municipio_tse_ibge",
  f"DESCRIBE SELECT * FROM read_parquet('{P}/municipio_tse_ibge/municipio_tse_ibge.parquet')")

q("Vereança 2024: Osasco x Barueri", """
WITH c AS (
  SELECT NM_MUNICIPIO m, SQ_CANDIDATO, any_value(DS_SIT_TOT_TURNO) sit,
         sum(CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT)) votos
  FROM v_votos_cand
  WHERE ano=2024 AND upper(DS_CARGO)='VEREADOR' AND NR_TURNO='1'
    AND upper(NM_MUNICIPIO) IN ('OSASCO','BARUERI')
  GROUP BY 1,2)
SELECT m, count(*) candidatos,
       count(*) FILTER (WHERE sit LIKE 'ELEITO%') eleitos,
       max(votos) FILTER (WHERE sit LIKE 'ELEITO%') maior_votacao,
       min(votos) FILTER (WHERE sit LIKE 'ELEITO%') menor_eleito,
       sum(votos) votos_nominais
FROM c GROUP BY m ORDER BY m""")

q("Eleitorado Osasco x Barueri por ano", """
SELECT ano, NM_MUNICIPIO, sum(CAST(QT_ELEITORES AS BIGINT)) eleitores,
       round(100.0*sum(CAST(QT_ELEITORES AS BIGINT)) FILTER (WHERE upper(DS_GENERO)='FEMININO')
             / sum(CAST(QT_ELEITORES AS BIGINT)), 1) pct_feminino
FROM v_perfil_mun WHERE upper(NM_MUNICIPIO) IN ('OSASCO','BARUERI')
GROUP BY 1,2 ORDER BY 2,1""")

q("Situação dos candidatos 2026 (SP)", """
SELECT DS_CARGO, DS_SIT_TOT_TURNO, count(*) n FROM v_cand
WHERE ano=2026 GROUP BY 1,2 ORDER BY 1,3 DESC LIMIT 15""")

q("Votação por seção: anos e cargos disponíveis", """
SELECT ano, DS_CARGO, count(*) linhas FROM v_votos_secao GROUP BY 1,2 ORDER BY 1,2""")
