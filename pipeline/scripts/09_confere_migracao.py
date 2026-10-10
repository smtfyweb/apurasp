import duckdb
con = duckdb.connect("data/apurasp.duckdb", read_only=True)

print("=== Mais votados p/ deputado estadual em 2022 (Barueri/Osasco) e partido do mesmo nome em 2026 ===")
rows = con.execute("""
 WITH t AS (SELECT NM_MUNICIPIO m, NM_URNA_CANDIDATO n, any_value(SG_PARTIDO) p22,
              sum(TRY_CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT)) v,
              row_number() OVER (PARTITION BY NM_MUNICIPIO
                                 ORDER BY sum(TRY_CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT)) DESC) rk
            FROM v_votos_cand
            WHERE ano=2022 AND NR_TURNO='1' AND upper(DS_CARGO)='DEPUTADO ESTADUAL'
              AND upper(NM_MUNICIPIO) IN ('BARUERI','OSASCO') GROUP BY 1,2)
 SELECT t.m, t.n, t.p22, t.v,
        (SELECT string_agg(DISTINCT c.SG_PARTIDO, '/') FROM v_cand c
         WHERE c.ano=2026 AND c.NM_URNA_CANDIDATO=t.n) p26
 FROM t WHERE rk<=3 ORDER BY 1, v DESC""").fetchall()
for r in rows: print(r)

print("\n=== Eleitos 2026 (federal+estadual) que em 2022 concorreram por outra sigla ===")
print(con.execute("""
 WITH a AS (SELECT DISTINCT NM_CANDIDATO n, SG_PARTIDO p22 FROM v_cand
            WHERE ano=2022 AND upper(DS_CARGO) IN ('DEPUTADO FEDERAL','DEPUTADO ESTADUAL'))
 SELECT count(DISTINCT b.SQ_CANDIDATO) eleitos,
        count(DISTINCT b.SQ_CANDIDATO) FILTER (WHERE a.p22 IS NOT NULL AND a.p22 <> b.SG_PARTIDO
          AND NOT EXISTS (SELECT 1 FROM a a2 WHERE a2.n=b.NM_CANDIDATO AND a2.p22=b.SG_PARTIDO)) trocaram_de_sigla
 FROM v_cand b LEFT JOIN a ON a.n=b.NM_CANDIDATO
 WHERE b.ano=2026 AND upper(b.DS_CARGO) IN ('DEPUTADO FEDERAL','DEPUTADO ESTADUAL')
   AND b.DS_SIT_TOT_TURNO LIKE 'ELEITO%'""").fetchall())
