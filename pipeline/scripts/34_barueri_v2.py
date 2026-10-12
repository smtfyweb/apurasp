import duckdb, collections, unicodedata, json, re
import pandas as pd

pd.set_option("display.width", 230); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
pd.set_option("display.float_format", lambda x: f"{x:,.1f}")
MUN, ANOS = "BARUERI", (2020, 2024)
con = duckdb.connect("data/apurasp.duckdb", read_only=True)
Q = lambda sql, *a: con.execute(sql, list(a)).fetchall()
NOTAS = json.load(open("public/data/partidos.json", encoding="utf-8"))

# incorporações e mudanças de nome (mapeamento do ApuraSP: confira antes de publicar)
SUCESSOR = {"DEM": "UNIÃO", "PSL": "UNIÃO", "PTB": "PRD", "PATRIOTA": "PRD", "PSC": "PODE", "PTC": "AGIR", "PMN": "MOBILIZA", "PROS": "SOLIDARIEDADE"}
CAMPO = {"extrema-esquerda": "esquerda", "esquerda": "esquerda", "centro-esquerda": "esquerda", "centro": "centro",
         "centro-direita": "direita", "direita": "direita", "extrema-direita": "direita"}
sa = lambda s: "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")
nsig = lambda s: "".join(c for c in sa(s).upper() if c.isalnum())
nn = lambda s: " ".join(re.sub(r"[^A-Z0-9 ]", "", sa(s).upper()).split())
fam = lambda p: SUCESSOR.get(p, p)
def classe(p): return NOTAS.get(nsig(p)) or NOTAS.get(nsig(SUCESSOR.get(p, "")))
campo = lambda p: (CAMPO.get(classe(p)[1]) if classe(p) else None)
nota = lambda p: (classe(p)[0] if classe(p) else None)
def fx(k):
    m = re.match(r"\s*(\d+)", k or ""); return int(m.group(1)) if m else None
def secao(t): print("\n" + "=" * 8, t, "=" * 8)
def rodar(t, fn):
    secao(t)
    try: fn()
    except Exception as e: print("   FALHOU:", type(e).__name__, str(e)[:300])

CAND = {}
for ano in ANOS:
    rows = Q("""SELECT sq, any_value(nome), any_value(urna), any_value(p), any_value(sit), sum(v) FROM (
        SELECT SQ_CANDIDATO sq, NR_ZONA z, any_value(NM_CANDIDATO) nome, any_value(NM_URNA_CANDIDATO) urna, any_value(SG_PARTIDO) p,
               any_value(DS_SIT_TOT_TURNO) sit,
               max(COALESCE(TRY_CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT), TRY_CAST(QT_VOTOS_NOMINAIS AS BIGINT), 0)) v
        FROM v_votos_cand WHERE ano = ? AND upper(DS_CARGO) = 'VEREADOR' AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ?
        GROUP BY SQ_CANDIDATO, NR_ZONA) GROUP BY sq""", ano, MUN)
    CAND[ano] = sorted([dict(sq=sq, nome=n or "", urna=u or "", p=p or "", sit=s or "", v=int(v or 0)) for sq, n, u, p, s, v in rows], key=lambda c: -c["v"])
eleito = lambda c: c["sit"].upper().startswith("ELEITO")
def legenda(ano):
    return Q("""SELECT p, sum(v) FROM (SELECT SG_PARTIDO p, NR_ZONA z, max(COALESCE(TRY_CAST(QT_VOTOS_LEGENDA_VALIDOS AS BIGINT), 0)) v
        FROM v_votos_partido WHERE ano = ? AND upper(DS_CARGO) = 'VEREADOR' AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ?
        GROUP BY SG_PARTIDO, NR_ZONA) GROUP BY p""", ano, MUN)
def totais(ano):
    nom = sum(c["v"] for c in CAND[ano]); leg = sum(x or 0 for _, x in legenda(ano))
    v = Q("""SELECT sum(v) FROM (SELECT NR_ZONA z, max(COALESCE(TRY_CAST(QT_TOTAL_VOTOS_VALIDOS AS BIGINT), 0)) v FROM v_detalhe
        WHERE ano = ? AND upper(DS_CARGO) = 'VEREADOR' AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ? GROUP BY NR_ZONA)""", ano, MUN)[0][0] or 0
    return (v or nom + leg), nom, leg
def votos_partido(ano):
    c = collections.Counter()
    for x in CAND[ano]: c[x["p"]] += x["v"]
    for p, v in legenda(ano): c[p] += v or 0
    return c
print(f"Barueri: {len(CAND[2020])} candidatos a vereador com votos em 2020 e {len(CAND[2024])} em 2024")

def s1():
    d = {}
    for ano in ANOS:
        votos, cad, memb = collections.Counter(), collections.Counter(), collections.defaultdict(set)
        for c in CAND[ano]:
            votos[fam(c["p"])] += c["v"]; memb[fam(c["p"])].add(c["p"])
            if eleito(c): cad[fam(c["p"])] += 1
        for p, x in legenda(ano): votos[fam(p)] += x or 0; memb[fam(p)].add(p)
        d[ano] = (votos, cad, memb, totais(ano)[0] or 1)
    linhas = []
    for f in set(d[2020][0]) | set(d[2024][0]):
        a, b = d[2020], d[2024]; v20, v24 = a[0].get(f, 0), b[0].get(f, 0)
        linhas.append({"família": f, "siglas em 2020": "+".join(sorted(a[2].get(f, set()))) or "-", "votos 2020": v20, "% 2020": 100 * v20 / a[3], "cad. 2020": a[1].get(f, 0),
                       "votos 2024": v24, "% 2024": 100 * v24 / b[3], "cad. 2024": b[1].get(f, 0),
                       "var. votos %": 100 * (v24 / v20 - 1) if v20 else None, "var. cadeiras": b[1].get(f, 0) - a[1].get(f, 0)})
    df = pd.DataFrame(linhas)
    df = df[(df["cad. 2020"] + df["cad. 2024"] > 0) | (df["% 2020"] >= 2) | (df["% 2024"] >= 2)]
    print(df.sort_values(["cad. 2024", "votos 2024"], ascending=False).to_string(index=False))
    print("(famílias: DEM+PSL no União, PTB no PRD, PSC no PODE; em 2024 as federações aparecem com cada partido separado)")

def s2():
    for ano in ANOS:
        votos = votos_partido(ano); cad = collections.Counter()
        for c in CAND[ano]:
            if eleito(c): cad[campo(c["p"]) or "sem classificação"] += 1
        t = sum(votos.values()) or 1; out = collections.Counter(); a = w = 0.0
        for p, x in votos.items():
            out[campo(p) or "sem classificação"] += x; n = nota(p)
            if n is not None: a += n * x; w += x
        ks = ("esquerda", "centro", "direita", "sem classificação")
        print(f"{ano}: votos -> " + " | ".join(f"{k} {100 * out[k] / t:.1f}%" for k in ks) + " | cadeiras -> " +
              ", ".join(f"{k} {cad[k]}" for k in ks if cad[k]) + (f" | nota média {a / w:.2f}" if w else ""))
        sem = sorted((p for p in votos if campo(p) is None and votos[p] / t >= 0.005), key=lambda p: -votos[p])
        if sem: print("   sem classificação:", ", ".join(f"{p} {100 * votos[p] / t:.1f}%" for p in sem))
    print("(classificação de 2022 dos partidos; DEM e PSL usam a nota do União. É o rótulo da legenda, não o do eleitor.)")

def s3():
    for ano in ANOS:
        votos, seats = collections.Counter(), collections.Counter()
        for c in CAND[ano]:
            votos[fam(c["p"])] += c["v"]
            if eleito(c): seats[fam(c["p"])] += 1
        for p, x in legenda(ano): votos[fam(p)] += x or 0
        tv, ts = sum(votos.values()) or 1, sum(seats.values()) or 1; top = votos.most_common(3)
        print(f"{ano}: número efetivo de partidos {1 / sum((x / tv) ** 2 for x in votos.values()):.1f} nos votos e {1 / sum((x / ts) ** 2 for x in seats.values()):.1f} nas cadeiras | "
              f"partidos com cadeira: {len(seats)} | maior: {top[0][0]} {100 * top[0][1] / tv:.1f}% | 3 maiores: {100 * sum(x for _, x in top) / tv:.1f}% dos votos")

def s4():
    for ano in ANOS:
        por, pv = collections.defaultdict(list), votos_partido(ano); linhas = []
        for c in CAND[ano]: por[c["p"]].append(c)
        for p, lst in por.items():
            n = sum(1 for c in lst if eleito(c))
            if not n or not pv[p]: continue
            top = lst[0]
            linhas.append({"partido": p, "votos": pv[p], "cadeiras": n, "puxador": top["urna"], "votos do puxador": top["v"],
                           "% do puxador nos votos do partido": 100 * top["v"] / pv[p], "% do partido que está nos eleitos": 100 * sum(c["v"] for c in lst if eleito(c)) / pv[p]})
        print(f"--- {ano} ---"); print(pd.DataFrame(linhas).sort_values("votos", ascending=False).to_string(index=False))

def s5():
    PN = {a: {nn(c["nome"]): c for c in reversed(CAND[a])} for a in ANOS}
    PU = {a: {nn(c["urna"]): c for c in reversed(CAND[a])} for a in ANOS}
    def achar(c, a):
        x = PN[a].get(nn(c["nome"]))
        if x: return x, ""
        y = PU[a].get(nn(c["urna"])); return (y, "*") if y else (None, "")
    def tipo(p1, p2): return "mesmo partido" if p1 == p2 else ("mesma família" if fam(p1) == fam(p2) else "troca de partido")
    def campo_mudou(p1, p2): return "-" if not (campo(p1) and campo(p2)) else ("mudou" if campo(p1) != campo(p2) else "igual")
    rows = []
    for c in [c for c in CAND[2020] if eleito(c)]:
        n, fl = achar(c, 2024)
        rows.append({"vereador(a) 2020": c["urna"], "partido 2020": c["p"], "votos 2020": c["v"], "partido 2024": n["p"] if n else "-", "votos 2024": n["v"] if n else None,
                     "variação %": 100 * (n["v"] / c["v"] - 1) if n and c["v"] else None,
                     "resultado 2024": ("eleito" if eleito(n) else "não eleito") if n else "sem registro", "partido": tipo(c["p"], n["p"]) if n else "-",
                     "campo": campo_mudou(c["p"], n["p"]) if n else "-", "casado por": ("nome de urna" if fl else "nome") if n else "-"})
    df = pd.DataFrame(rows); print("--- Eleitos de 2020 ---"); print(df.to_string(index=False))
    ran = df[df["resultado 2024"] != "sem registro"]; ree = ran[ran["resultado 2024"] == "eleito"]
    print(f"\nde {len(df)} eleitos em 2020: {len(ran)} aparecem em 2024, {len(ree)} reeleitos | mesmo partido {int((ran.partido == 'mesmo partido').sum())}, "
          f"mesma família (incorporação ou renomeação) {int((ran.partido == 'mesma família').sum())}, troca de partido {int((ran.partido == 'troca de partido').sum())} | "
          f"campo mudou em {int((ran.campo == 'mudou').sum())} de {int((ran.campo != '-').sum())} casos classificáveis")
    print(f"mediana da variação de votos dos reeleitos: {ree['variação %'].median():+.0f}% (votos válidos totais: {100 * (totais(2024)[0] / totais(2020)[0] - 1):+.0f}%)")
    print("sem registro em 2024:", ", ".join(df[df["resultado 2024"] == "sem registro"]["vereador(a) 2020"]), "(podem ter concorrido com outro nome)")
    rows = []
    for c in [c for c in CAND[2024] if eleito(c)]:
        a, fl = achar(c, 2020)
        rows.append({"vereador(a) 2024": c["urna"], "partido 2024": c["p"], "votos 2024": c["v"], "em 2020": ("eleito" if eleito(a) else "não eleito") if a else "sem registro",
                     "partido 2020": a["p"] if a else "-", "votos 2020": a["v"] if a else None, "casado por": ("nome de urna" if fl else "nome") if a else "-"})
    df2 = pd.DataFrame(rows); print("\n--- Eleitos de 2024 ---"); print(df2.to_string(index=False))
    print(f"\nde {len(df2)} eleitos em 2024: {int((df2['em 2020'] == 'eleito').sum())} já eram vereadores, {int((df2['em 2020'] == 'não eleito').sum())} concorreram em 2020 sem se eleger, {int((df2['em 2020'] == 'sem registro').sum())} sem registro em 2020")
    print("(casado por 'nome de urna' = confira à mão: o mesmo apelido pode ser de outra pessoa)")

def s6():
    for ano in ANOS:
        rows = Q("""SELECT t, sq, any_value(urna), any_value(p), any_value(sit), sum(v) FROM (
            SELECT NR_TURNO t, SQ_CANDIDATO sq, NR_ZONA z, any_value(NM_URNA_CANDIDATO) urna, any_value(SG_PARTIDO) p, any_value(DS_SIT_TOT_TURNO) sit,
                   max(COALESCE(TRY_CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT), TRY_CAST(QT_VOTOS_NOMINAIS AS BIGINT), 0)) v
            FROM v_votos_cand WHERE ano = ? AND upper(DS_CARGO) = 'PREFEITO' AND upper(NM_MUNICIPIO) = ? GROUP BY NR_TURNO, SQ_CANDIDATO, NR_ZONA)
            GROUP BY t, sq""", ano, MUN)
        por = collections.defaultdict(list)
        for t, sq, u, p, sit, v in rows: por[t].append((u, p, sit or "", int(v or 0)))
        for t in sorted(por):
            lst = sorted(por[t], key=lambda x: -x[3]); tot = sum(x[3] for x in lst) or 1
            print(f"{ano}, turno {t}: " + " | ".join(f"{u} ({p}) {v:,} = {100 * v / tot:.1f}%{' [eleito]' if s.startswith('ELEITO') else ''}" for u, p, s, v in lst[:3]))

def s7():
    cols = {}
    for ano in (2020, 2022, 2024, 2026):
        rows = Q("""SELECT DS_GENERO, DS_FAIXA_ETARIA, DS_GRAU_ESCOLARIDADE,
                           sum(COALESCE(TRY_CAST(QT_ELEITORES AS BIGINT), TRY_CAST(QT_ELEITORES_PERFIL AS BIGINT), 0))
                    FROM v_perfil_mun WHERE ano = ? AND upper(NM_MUNICIPIO) = ? GROUP BY ALL""", ano, MUN)
        t = sum(r[3] for r in rows)
        if not t: print(f"   {ano}: sem dados"); continue
        idade = lambda lo, hi: sum(r[3] for r in rows if (a := fx(r[1])) is not None and lo <= a <= hi)
        esc = lambda pref: sum(r[3] for r in rows if (r[2] or "").upper().startswith(pref))
        cols[ano] = {"eleitores": t, "mulheres %": 100 * sum(r[3] for r in rows if (r[0] or "").upper() == "FEMININO") / t,
                     "16 a 24 anos %": 100 * idade(16, 24) / t, "25 a 44 anos %": 100 * idade(25, 44) / t, "45 a 59 anos %": 100 * idade(45, 59) / t,
                     "60 anos ou mais %": 100 * idade(60, 200) / t, "superior completo %": 100 * esc("SUPERIOR COMPLETO") / t}
    df = pd.DataFrame(cols); print(df.to_string())
    if 2020 in cols and 2024 in cols: print(f"\neleitorado 2020 -> 2024: {100 * (cols[2024]['eleitores'] / cols[2020]['eleitores'] - 1):+.1f}% | 2024 -> 2026: " +
                                            (f"{100 * (cols[2026]['eleitores'] / cols[2024]['eleitores'] - 1):+.1f}%" if 2026 in cols else "-"))

GRUPOS = [("16 e 17 anos", 0, 17), ("18 a 24 anos", 18, 24), ("25 a 34 anos", 25, 34), ("35 a 44 anos", 35, 44), ("45 a 59 anos", 45, 59), ("60 a 69 anos", 60, 69), ("70 anos ou mais", 70, 200)]
def esc_grupo(s):
    u = (s or "").upper()
    if u.startswith("SUPERIOR"): return "superior"
    if u.startswith("ENSINO MÉDIO") or u.startswith("ENSINO MEDIO"): return "médio"
    if u in ("ANALFABETO", "LÊ E ESCREVE") or u.startswith("ENSINO FUNDAMENTAL"): return "até fundamental"
    return None
def s8():
    for ano in (2022, 2024):
        rows = Q("""SELECT DS_FAIXA_ETARIA, DS_GRAU_ESCOLARIDADE, upper(DS_GENERO), sum(TRY_CAST(QT_APTOS AS BIGINT)), sum(TRY_CAST(QT_ABSTENCAO AS BIGINT))
                    FROM v_comparecimento WHERE ano = ? AND upper(NM_MUNICIPIO) = ? AND NR_TURNO = '1' GROUP BY ALL""", ano, MUN)
        if not rows: print(f"{ano}: sem dados"); continue
        T, A = sum(r[3] or 0 for r in rows), sum(r[4] or 0 for r in rows)
        print(f"\n{ano}, 1º turno: {T:,} aptos | abstenção {100 * A / T:.1f}%")
        def tabela(chave, ordem):
            d = collections.defaultdict(lambda: [0, 0])
            for r in rows:
                g = chave(r)
                if g: d[g][0] += r[3] or 0; d[g][1] += r[4] or 0
            return pd.DataFrame([{"grupo": g, "aptos": d[g][0], "abstenções": d[g][1], "taxa %": 100 * d[g][1] / d[g][0] if d[g][0] else None} for g in ordem if g in d]).set_index("grupo")
        faixa = lambda r: next((n for n, lo, hi in GRUPOS if fx(r[0]) is not None and lo <= fx(r[0]) <= hi), None)
        print(tabela(faixa, [g[0] for g in GRUPOS]).to_string())
        print(tabela(lambda r: esc_grupo(r[1]), ["até fundamental", "médio", "superior"]).to_string())
        print(tabela(lambda r: r[2] if r[2] in ("FEMININO", "MASCULINO") else None, ["FEMININO", "MASCULINO"]).to_string())
    print("\n(só município e zona: o TSE não divulga esse recorte por seção. 16 e 17 anos e 70+ votam por opção.)")

rodar("1. Famílias partidárias (com sucessores): votos e cadeiras", s1)
rodar("2. Campo político da vereança", s2)
rodar("3. Fragmentação", s3)
rodar("4. O puxador de cada partido", s4)
rodar("5. Continuidade, troca de partido e troca de campo", s5)
rodar("6. Prefeito", s6)
rodar("7. Eleitorado de Barueri, 2020 a 2026", s7)
rodar("8. Abstenção por perfil (agregada)", s8)
