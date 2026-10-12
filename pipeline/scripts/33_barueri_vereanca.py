import duckdb, collections, unicodedata, pathlib
import pandas as pd

pd.set_option("display.width", 230); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
pd.set_option("display.float_format", lambda x: f"{x:,.1f}")
con = duckdb.connect("data/apurasp.duckdb", read_only=True)
Q = lambda sql, *a: con.execute(sql, list(a)).fetchall()
MUN, ANOS = "BARUERI", (2020, 2024)

def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s.upper() if (c.isalnum() or c == " ") and unicodedata.category(c) != "Mn").strip()
def secao(t): print("\n" + "=" * 8, t, "=" * 8)
def rodar(t, fn):
    secao(t)
    try: fn()
    except Exception as e: print("   FALHOU:", type(e).__name__, str(e)[:300])
def qe_de(v, n):
    q, r = divmod(v, n); return q + (1 if 2 * r > n else 0)   # fração até 0,5 é desprezada; acima de 0,5 vale um

CAND = {}
for ano in ANOS:
    rows = Q("""SELECT sq, any_value(nome), any_value(urna), any_value(p), any_value(sit), sum(v) FROM (
        SELECT SQ_CANDIDATO sq, NR_ZONA z, any_value(NM_CANDIDATO) nome, any_value(NM_URNA_CANDIDATO) urna, any_value(SG_PARTIDO) p,
               any_value(DS_SIT_TOT_TURNO) sit,
               max(COALESCE(TRY_CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT), TRY_CAST(QT_VOTOS_NOMINAIS AS BIGINT), 0)) v
        FROM v_votos_cand WHERE ano = ? AND upper(DS_CARGO) = 'VEREADOR' AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ?
        GROUP BY SQ_CANDIDATO, NR_ZONA) GROUP BY sq""", ano, MUN)
    CAND[ano] = sorted([dict(sq=sq, nome=n or "", urna=u or "", p=p or "", sit=sit or "", v=int(v or 0)) for sq, n, u, p, sit, v in rows], key=lambda c: -c["v"])
eleito = lambda c: c["sit"].upper().startswith("ELEITO")
PN = {ano: {norm(c["nome"]): c for c in reversed(CAND[ano])} for ano in ANOS}     # em homônimos, fica o mais votado

def legenda(ano):
    return Q("""SELECT p, sum(v) FROM (SELECT SG_PARTIDO p, NR_ZONA z, max(COALESCE(TRY_CAST(QT_VOTOS_LEGENDA_VALIDOS AS BIGINT), 0)) v
        FROM v_votos_partido WHERE ano = ? AND upper(DS_CARGO) = 'VEREADOR' AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ?
        GROUP BY SG_PARTIDO, NR_ZONA) GROUP BY p""", ano, MUN)
def totais(ano):
    nom = sum(c["v"] for c in CAND[ano]); leg = sum(x or 0 for _, x in legenda(ano))
    v = Q("""SELECT sum(v) FROM (SELECT NR_ZONA z, max(COALESCE(TRY_CAST(QT_TOTAL_VOTOS_VALIDOS AS BIGINT), 0)) v FROM v_detalhe
        WHERE ano = ? AND upper(DS_CARGO) = 'VEREADOR' AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ? GROUP BY NR_ZONA)""", ano, MUN)[0][0] or 0
    return (v or nom + leg), nom, leg
print(f"Barueri: {len(CAND[2020])} candidatos a vereador em 2020 e {len(CAND[2024])} em 2024")

def q1():
    col = {}
    for ano in ANOS:
        lst = CAND[ano]; v, nom, leg = totais(ano); n = sum(1 for c in lst if eleito(c))
        if not n: print(f"   {ano}: nenhum eleito encontrado"); continue
        qe = qe_de(v, n); el = [c["v"] for c in lst if eleito(c)]; nel = [c["v"] for c in lst if not eleito(c) and not c["sit"].startswith("#")]
        col[ano] = {"votos válidos": v, "candidatos": len(lst), "cadeiras": n, "quociente eleitoral": qe, "10% do quociente": -(-qe * 10 // 100),
                    "votos de legenda (%)": 100 * leg / v if v else None, "5 mais votados (% dos válidos)": 100 * sum(c["v"] for c in lst[:5]) / v if v else None,
                    "candidatos com 10% do quociente": sum(1 for c in lst if c["v"] >= 0.1 * qe),
                    "menos votado entre os eleitos": min(el), "mais votado entre os não eleitos": max(nel) if nel else None}
    df = pd.DataFrame(col)
    if 2020 in col and 2024 in col: df["variação"] = df[2024] - df[2020]
    print(df.to_string())

def q2():
    d = {}
    for ano in ANOS:
        v, nom, leg = totais(ano); votos, cad = collections.Counter(), collections.Counter()
        for c in CAND[ano]:
            votos[c["p"]] += c["v"]
            if eleito(c): cad[c["p"]] += 1
        for p, x in legenda(ano): votos[p] += x or 0
        d[ano] = (votos, cad, v or 1)
    linhas = []
    for p in set(d[2020][0]) | set(d[2024][0]):
        a, b = d[2020], d[2024]; v20, v24 = a[0].get(p, 0), b[0].get(p, 0)
        linhas.append({"partido": p, "votos 2020": v20, "% 2020": 100 * v20 / a[2], "cadeiras 2020": a[1].get(p, 0), "votos 2024": v24, "% 2024": 100 * v24 / b[2],
                       "cadeiras 2024": b[1].get(p, 0), "variação votos (%)": 100 * (v24 / v20 - 1) if v20 else None, "variação cadeiras": b[1].get(p, 0) - a[1].get(p, 0)})
    df = pd.DataFrame(linhas)
    df = df[(df["cadeiras 2020"] + df["cadeiras 2024"] > 0) | (df["% 2020"] >= 2) | (df["% 2024"] >= 2)]
    print(df.sort_values(["cadeiras 2024", "votos 2024"], ascending=False).to_string(index=False))
    print("(votos do partido = votos nos candidatos + votos de legenda; em 2024 existem federações, e aqui cada partido aparece separado)")

def q3():
    print("--- Eleitos de 2020: o que aconteceu em 2024 (casamento por nome completo) ---")
    rows = []
    for c in [c for c in CAND[2020] if eleito(c)]:
        n = PN[2024].get(norm(c["nome"]))
        rows.append({"vereador(a) 2020": c["urna"], "partido 2020": c["p"], "votos 2020": c["v"], "partido 2024": n["p"] if n else "-", "votos 2024": n["v"] if n else None,
                     "variação (%)": 100 * (n["v"] / c["v"] - 1) if n and c["v"] else None,
                     "resultado 2024": ("eleito" if eleito(n) else "não eleito") if n else "não concorreu (ou outro nome)"})
    print(pd.DataFrame(rows).to_string(index=False))
    conc = sum(1 for r in rows if r["votos 2024"] is not None); ree = sum(1 for r in rows if r["resultado 2024"] == "eleito")
    troc = sum(1 for r in rows if r["resultado 2024"] == "eleito" and r["partido 2020"] != r["partido 2024"])
    print(f"de {len(rows)} eleitos em 2020: {conc} concorreram de novo, {ree} foram reeleitos, {troc} dos reeleitos mudaram de partido")
    print("\n--- Eleitos de 2024: de onde vieram ---")
    rows = []
    for c in [c for c in CAND[2024] if eleito(c)]:
        a = PN[2020].get(norm(c["nome"]))
        rows.append({"vereador(a) 2024": c["urna"], "partido 2024": c["p"], "votos 2024": c["v"],
                     "em 2020": ("eleito" if eleito(a) else "não eleito") if a else "não concorreu (ou outro nome)",
                     "partido 2020": a["p"] if a else "-", "votos 2020": a["v"] if a else None,
                     "variação (%)": 100 * (c["v"] / a["v"] - 1) if a and a["v"] else None})
    print(pd.DataFrame(rows).to_string(index=False))
    novos = sum(1 for r in rows if r["em 2020"].startswith("não concorreu")); der = sum(1 for r in rows if r["em 2020"] == "não eleito")
    print(f"de {len(rows)} eleitos em 2024: {sum(1 for r in rows if r['em 2020'] == 'eleito')} já eram vereadores, {der} tinham concorrido em 2020 sem se eleger, {novos} sem registro em 2020")
    print("\n--- 15 mais votados de 2024 e a votação deles em 2020 ---")
    rows = []
    for c in CAND[2024][:15]:
        a = PN[2020].get(norm(c["nome"]))
        rows.append({"candidato 2024": c["urna"], "partido": c["p"], "votos 2024": c["v"], "eleito": "sim" if eleito(c) else "não",
                     "votos 2020": a["v"] if a else None, "partido 2020": a["p"] if a else "-"})
    print(pd.DataFrame(rows).to_string(index=False))

def q4():
    for ano in ANOS:
        if ano == 2020:
            f = pathlib.Path("data/parquet/consulta_cand/consulta_cand_2020_BARUERI.parquet")
            if not f.exists(): print("   sem consulta_cand de 2020"); continue
            src, filtro, args = f"read_parquet('{f}')", "upper(DS_CARGO) = 'VEREADOR'", []
        else:
            src, filtro, args = "v_cand", "ano = ? AND upper(NM_UE) = ? AND upper(DS_CARGO) = 'VEREADOR'", [ano, MUN]
        rows = con.execute(f"""SELECT upper(DS_GENERO), count(DISTINCT SQ_CANDIDATO), count(DISTINCT SQ_CANDIDATO) FILTER (WHERE DS_SIT_TOT_TURNO LIKE 'ELEITO%')
                               FROM {src} WHERE {filtro} GROUP BY 1""", args).fetchall()
        t, e = sum(r[1] for r in rows), sum(r[2] for r in rows)
        print(f"{ano}: " + " | ".join(f"{g}: {c} candidatos, {el} eleitos" for g, c, el in rows) +
              "".join(f" | mulheres: {100 * c / t:.0f}% das candidaturas e {100 * el / max(1, e):.0f}% dos eleitos" for g, c, el in rows if g.startswith("FEM")))

def q5():
    f = pathlib.Path("data/parquet/perfil_eleitorado/perfil_eleitorado_2020_BARUERI.parquet")
    for ano, src, filtro, args in ((2020, f"read_parquet('{f}')", "TRUE", []), (2024, "v_perfil_mun", "ano = 2024 AND upper(NM_MUNICIPIO) = ?", [MUN])):
        if ano == 2020 and not f.exists(): print("   sem perfil do eleitorado de 2020"); continue
        t, fem = con.execute(f"""SELECT sum(TRY_CAST(QT_ELEITORES AS BIGINT)), sum(TRY_CAST(QT_ELEITORES AS BIGINT)) FILTER (WHERE upper(DS_GENERO) = 'FEMININO')
                                 FROM {src} WHERE {filtro}""", args).fetchone()
        print(f"{ano}: {t:,} eleitores | mulheres {100 * fem / t:.1f}%")

rodar("1. Quociente e concentração: 2020 x 2024", q1)
rodar("2. Partidos: quem cresceu e quem caiu", q2)
rodar("3. Continuidade: reeleições, derrotas, estreantes e trocas de partido", q3)
rodar("4. Gênero de candidatos e eleitos", q4)
rodar("5. Eleitorado de Barueri", q5)
