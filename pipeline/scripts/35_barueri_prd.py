import duckdb, collections, json, re, pathlib, unicodedata
import pandas as pd

pd.set_option("display.width", 230); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
pd.set_option("display.float_format", lambda x: f"{x:,.2f}" if abs(x) < 100 else f"{x:,.0f}")
MUN, N_VAGAS = "BARUERI", 21
LIMITE_LISTA = N_VAGAS + 1       # cada partido ou federação pode registrar até 100% das vagas + 1 (confirme o texto vigente da Lei 9.504/97, art. 10)
RS, UP = "RENOVAÇÃO SOLIDÁRIA (PRD+SOLIDARIEDADE)", "UNIÃO PROGRESSISTA (UNIÃO+PP)"
con = duckdb.connect("data/apurasp.duckdb", read_only=True)
Q = lambda sql, *a: con.execute(sql, list(a)).fetchall()
nz = lambda c: f"CASE WHEN trim({c}) IN ('', '#NULO#', '#NULO', '#NE#', '#NE') THEN NULL ELSE trim({c}) END"
sa = lambda s: "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")
nn = lambda s: " ".join(re.sub(r"[^A-Z0-9 ]", "", sa(s).upper()).split())
elet = lambda c: (c[3] or "").upper().startswith("ELEITO")
def qe_de(v, n):
    q, r = divmod(v, n); return q + (1 if 2 * r > n else 0)   # fração até 0,5 é desprezada; acima de 0,5 vale um
def secao(t): print("\n" + "=" * 8, t, "=" * 8)
def rodar(t, fn):
    secao(t)
    try: fn()
    except Exception as e: print("   FALHOU:", type(e).__name__, str(e)[:300])

def carregar(ano):
    cand = Q(f"""SELECT sq, any_value(urna), any_value(part), any_value(fed), any_value(sit), any_value(nome), sum(v) FROM (
        SELECT SQ_CANDIDATO sq, NR_ZONA z, any_value(NM_URNA_CANDIDATO) urna, any_value(SG_PARTIDO) part, any_value({nz('SG_FEDERACAO')}) fed,
               any_value(DS_SIT_TOT_TURNO) sit, any_value(NM_CANDIDATO) nome,
               max(COALESCE(TRY_CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT), TRY_CAST(QT_VOTOS_NOMINAIS AS BIGINT), 0)) v
        FROM v_votos_cand WHERE ano = ? AND upper(DS_CARGO) = 'VEREADOR' AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ?
        GROUP BY SQ_CANDIDATO, NR_ZONA) GROUP BY sq""", ano, MUN)
    leg = Q(f"""SELECT part, fed, sum(v) FROM (
        SELECT SG_PARTIDO part, {nz('SG_FEDERACAO')} fed, NR_ZONA z, max(COALESCE(TRY_CAST(QT_VOTOS_LEGENDA_VALIDOS AS BIGINT), 0)) v
        FROM v_votos_partido WHERE ano = ? AND upper(DS_CARGO) = 'VEREADOR' AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ?
        GROUP BY ALL) GROUP BY part, fed""", ano, MUN)
    val = Q("""SELECT sum(v) FROM (SELECT NR_ZONA z, max(COALESCE(TRY_CAST(QT_TOTAL_VOTOS_VALIDOS AS BIGINT), 0)) v FROM v_detalhe
        WHERE ano = ? AND upper(DS_CARGO) = 'VEREADOR' AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ? GROUP BY NR_ZONA)""", ano, MUN)[0][0] or 0
    U = {}
    novo = lambda: {"c": [], "leg": 0, "of": 0, "partes": set()}
    for sq, urna, part, fed, sit, nome, v in cand:
        u = U.setdefault(fed or part, novo()); u["partes"].add(part)
        u["c"].append((int(v or 0), urna or "", part, sit or "", nome or ""))
        if (sit or "").upper().startswith("ELEITO"): u["of"] += 1
    for part, fed, v in leg:
        u = U.setdefault(fed or part, novo()); u["leg"] += int(v or 0); u["partes"].add(part)
    for u in U.values():
        u["c"].sort(key=lambda x: -x[0]); u["cv"] = [x[0] for x in u["c"]]; u["v"] = sum(u["cv"]) + u["leg"]
    return U, val, qe_de(val, N_VAGAS)
U20, V20, QE20 = carregar(2020); U24, V24, QE24 = carregar(2024)
print(f"2020: votos válidos {V20:,} | quociente {QE20:,} | eleitos {sum(u['of'] for u in U20.values())} | unidades {len(U20)}")
print(f"2024: votos válidos {V24:,} | quociente {QE24:,} | eleitos {sum(u['of'] for u in U24.values())} | unidades {len(U24)} (federações contam como uma)")

def alocar(units, qe, n):
    """quociente partidário (com piso de 10% do quociente para o candidato) e sobras pelas maiores médias:
    1ª fase das sobras com 80% (partido) e 20% (candidato); se sobrarem cadeiras, todos concorrem (decisão do STF nas ADIs 7228, 7263 e 7325)"""
    seats = {k: int(min(u["v"] // qe, sum(1 for x in u["cv"] if x >= 0.1 * qe))) for k, u in units.items()}
    ordem, faltam = [], n - sum(seats.values())
    def ok(k, fase):
        u = units[k]
        if seats[k] >= len(u["cv"]): return False
        return (u["v"] >= 0.8 * qe and u["cv"][seats[k]] >= 0.2 * qe) if fase == 2 else True
    while faltam > 0:
        el, fase = [k for k in units if ok(k, 2)], 2
        if not el: el, fase = [k for k in units if ok(k, 3)], 3
        if not el: break
        k = max(el, key=lambda x: units[x]["v"] / (seats[x] + 1))
        ordem.append((k, units[k]["v"] / (seats[k] + 1), fase)); seats[k] += 1; faltam -= 1
    return seats, ordem
mk = lambda U: {k: {"v": u["v"], "cv": u["cv"]} for k, u in U.items()}

def validar(ano, U, qe):
    units = mk(U); sim, ordem = alocar(units, qe, N_VAGAS)
    dif = [(k, u["of"], sim[k]) for k, u in U.items() if u["of"] != sim[k]]
    print(f"{ano}: a simulação {'REPRODUZ' if not dif else 'NÃO REPRODUZ'} o resultado oficial" + (f" | divergências (unidade, oficial, simulado): {dif}" if dif else ""))
    if ordem:
        k, m, f = ordem[-1]
        perd = [(units[x]["v"] / (sim[x] + 1), x) for x in units if sim[x] < len(units[x]["cv"])]
        mp = max(perd) if perd else None
        print(f"   última cadeira por média: {k} (média {m:,.0f}, fase {f}) | maior média que ficou de fora: " + (f"{mp[1]} ({mp[0]:,.0f})" if mp else "-"))
    return not dif

def minimo(units, k, qe, passo=50, teto=15000):
    base = units[k]["cv"]
    for N in range(passo, teto + 1, passo):
        u2 = dict(units); u2[k] = {"v": units[k]["v"] + N, "cv": sorted(base + [N], reverse=True)}
        sim, _ = alocar(u2, qe, N_VAGAS)
        if sum(1 for x in base if x >= N) < sim[k]: return N      # empate de votos conta contra
    return None
def fundir(U, chaves, nome, corte=None):
    out = {k: u for k, u in U.items() if k not in chaves}
    cs = sorted([x for k in chaves if k in U for x in U[k]["c"]], key=lambda x: -x[0])
    if corte: cs = cs[:corte]
    cv = [x[0] for x in cs]; leg = sum(U[k]["leg"] for k in chaves if k in U)
    out[nome] = {"c": cs, "cv": cv, "leg": leg, "v": sum(cv) + leg, "of": 0, "partes": set().union(*[U[k]["partes"] for k in chaves if k in U])}
    return out
def escalar(units, g, k, f):
    return {kk: {"v": int(round(u["v"] * g * (f if kk == k else 1))), "cv": [int(round(x * g * (f if kk == k else 1))) for x in u["cv"]]} for kk, u in units.items()}

def s1():
    fam = [k for k in ("PTB", "PATRIOTA") if k in U20]; u = U24.get("PRD")
    if not fam or not u: print("   PTB ou PRD não encontrado"); return
    v20 = sum(U20[k]["v"] for k in fam)
    print(f"2020 ({'+'.join(fam)}): {v20:,} votos = {v20 / QE20:.2f} quociente | {sum(U20[k]['of'] for k in fam)} cadeiras | {sum(len(U20[k]['c']) for k in fam)} candidatos")
    print(f"2024 (PRD): {u['v']:,} votos = {u['v'] / QE24:.2f} quociente | {u['of']} cadeira(s) | {len(u['c'])} candidatos | legenda {u['leg']:,}")
    PN24 = {nn(c[4]): c for uu in U24.values() for c in uu["c"]}; PN20 = {nn(c[4]): c for uu in U20.values() for c in uu["c"]}
    linhas = []
    for k in fam:
        for c in U20[k]["c"][:10]:
            n = PN24.get(nn(c[4]))
            linhas.append({"candidato 2020": c[1], "partido 2020": c[2], "votos 2020": c[0], "2020": "eleito" if elet(c) else "não eleito",
                           "partido 2024": n[2] if n else "-", "votos 2024": n[0] if n else None, "2024": ("eleito" if elet(n) else "não eleito") if n else "sem registro"})
    print("\n--- Os 10 mais votados do PTB em 2020 e o que fizeram em 2024 (casamento por nome completo) ---"); print(pd.DataFrame(linhas).to_string(index=False))
    linhas = []
    for c in u["c"][:12]:
        a = PN20.get(nn(c[4]))
        linhas.append({"candidato PRD 2024": c[1], "votos": c[0], "% do quociente": 100 * c[0] / QE24, "2024": "eleito" if elet(c) else "não eleito",
                       "em 2020": f"{a[2]} ({a[0]:,})" if a else "sem registro"})
    print("\n--- Candidatos do PRD em 2024 ---"); print(pd.DataFrame(linhas).to_string(index=False))

def s2():
    r20, r24 = validar(2020, U20, QE20), validar(2024, U24, QE24)
    if not (r20 and r24): print("   ATENÇÃO: a simulação diverge do resultado oficial; trate os mínimos de votos abaixo como aproximações.")

def s3():
    linhas = []
    for k, u in U24.items():
        s, cv = u["of"], u["cv"]
        linhas.append({"unidade": k, "partidos": "+".join(sorted(u["partes"])), "votos": u["v"], "votos ÷ QE": u["v"] / QE24, "cadeiras": s, "candidatos": len(cv),
                       "acima de 10% do QE": sum(1 for x in cv if x >= 0.1 * QE24), "último eleito": cv[s - 1] if s else None,
                       "1º que ficou de fora": cv[s] if len(cv) > s else None, "sobrando (>= último eleito)": sum(1 for x in cv[s:] if s and x >= cv[s - 1])})
    print(pd.DataFrame(linhas).sort_values("votos", ascending=False).to_string(index=False))

def s4():
    cen = (("2024 como foi (listas separadas)", U24, ("PRD", "SOLIDARIEDADE", "UNIÃO", "PP")),
           ("2028 com as federações, mesmos votos de 2024", fundir(fundir(U24, ["PRD", "SOLIDARIEDADE"], RS), ["UNIÃO", "PP"], UP), (RS, UP)),
           (f"2028 com as federações, só os {LIMITE_LISTA} mais votados de cada lista (os outros votos somem)",
            fundir(fundir(U24, ["PRD", "SOLIDARIEDADE"], RS, LIMITE_LISTA), ["UNIÃO", "PP"], UP, LIMITE_LISTA), (RS, UP)))
    for rot, UU, chaves in cen:
        units = mk(UU); sim, ordem = alocar(units, QE24, N_VAGAS)
        print(f"\n--- {rot} ---")
        for k in chaves:
            mn = minimo(units, k, QE24)
            print(f"   {k:<42} {units[k]['v']:>7,} votos ({units[k]['v'] / QE24:4.2f} QE) | cadeiras {sim[k]} | mínimo de votos pessoais para se eleger por essa lista: {f'{mn:,}' if mn else 'acima de 15.000'}")
        if ordem: print(f"   última cadeira por média: {ordem[-1][0]} (média {ordem[-1][1]:,.0f})")
        if RS in UU and "sem os" not in rot:
            print(f"   lista ordenada de {RS}:")
            for i, c in enumerate(UU[RS]["c"][:8]): print(f"      {i + 1}º {c[1]:<24} {c[2]:<14} {c[0]:>6,}{'   <- cadeira' if i < sim[RS] else ''}")

def s5():
    UU = fundir(fundir(U24, ["PRD", "SOLIDARIEDADE"], RS), ["UNIÃO", "PP"], UP); units = mk(UU)
    print(f"{RS}: f = desempenho da federação em relação aos demais; g = crescimento dos votos válidos (e do quociente). Cada célula: cadeiras | mínimo de votos pessoais.")
    for f in (0.7, 0.85, 1.0, 1.15, 1.3):
        cel = []
        for g in (1.0, 1.1, 1.2):
            u2 = escalar(units, g, RS, f); qe2 = int(round(QE24 * g)); sim, _ = alocar(u2, qe2, N_VAGAS)
            mn = minimo(u2, RS, qe2); cel.append(f"g +{int(round((g - 1) * 100))}%: {sim[RS]} cad. | {f'{mn:,}' if mn else '>15.000'}")
        print(f"   f {int(round((f - 1) * 100)):+d}%:  " + "   ".join(cel))

def s6():
    f = pathlib.Path("public/data/micro/3505708.json")
    if not f.exists(): print("   sem o arquivo do mapa por local de Barueri (script 18)"); return
    mi = json.load(open(f, encoding="utf-8")); blk = (mi.get("votos", {}).get("2024") or {}).get("vereador1"); locs = (mi.get("locais") or {}).get("2024") or []
    if not blk: print("   sem votos de vereador 2024 por local"); return
    b = [(l.get("b") or "Sem bairro") for l in locs]; val = collections.Counter()
    for j, nome in enumerate(b): val[nome] += blk["val"][j]
    tv = sum(val.values()); idx = {sg: i for i, (sg, _) in enumerate(blk["p"])}
    for sg in ("PRD", "SOLIDARIEDADE", "REPUBLICANOS"):
        if sg not in idx: print(f"   {sg}: sem votos por local"); continue
        pb = collections.Counter()
        for j, nome in enumerate(b): pb[nome] += blk["pv"][idx[sg]][j]
        tot = sum(pb.values()); lista = sorted([(n, 100 * pb[n] / val[n], pb[n]) for n in val if val[n] >= 1500], key=lambda x: -x[1])
        print(f"\n{sg}: {tot:,} votos ({100 * tot / tv:.1f}% dos válidos de Barueri) | 5 bairros reúnem {100 * sum(sorted(pb.values(), reverse=True)[:5]) / max(1, tot):.0f}% dos votos do partido")
        print("   mais fortes (% dos válidos do bairro): " + ", ".join(f"{n} {s:.1f}%" for n, s, _ in lista[:6]))
        print("   mais fracos: " + ", ".join(f"{n} {s:.1f}%" for n, s, _ in lista[-4:]))
        print("   mais votos absolutos: " + ", ".join(f"{n} {v:,}" for n, v in pb.most_common(5)))

rodar("1. A família PTB → PRD em Barueri", s1)
rodar("2. Validação: a simulação reproduz o resultado oficial?", s2)
rodar("3. Preço de entrada de cada partido ou federação (2024)", s3)
rodar("4. 2028 com federações: cadeiras e votos pessoais necessários", s4)
rodar("5. Sensibilidade da federação PRD+Solidariedade", s5)
rodar("6. Onde estão as bases (por bairro, agregado)", s6)
print("\nPremissas: os demais votos ficam como em 2024; o candidato hipotético soma votos novos à lista (sem tirar de colegas); o quociente só muda onde indicado; "
      "o empate de votos conta contra. É um mapa de custo de entrada, não uma previsão.")
