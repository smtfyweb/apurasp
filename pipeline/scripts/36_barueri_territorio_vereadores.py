import duckdb, json, collections
import pandas as pd

pd.set_option("display.width", 230); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
pd.set_option("display.float_format", lambda x: f"{x:,.1f}")
MUN, COD, MIN_VAL = "BARUERI", "3505708", 1500
FOCO = ("LEVI JANIO", "GENTE DA GENTE")      # trechos do nome de urna dos vereadores acompanhados
con = duckdb.connect("data/apurasp.duckdb", read_only=True)
Q = lambda sql, *a: con.execute(sql, list(a)).fetchall()
micro = json.load(open(f"public/data/micro/{COD}.json", encoding="utf-8"))
locs = micro["locais"]["2024"]; blk = micro["votos"]["2024"]["vereador1"]
bairro_de = {l["id"]: (l.get("b") or "Sem bairro") for l in locs}
val = collections.Counter()
for j, l in enumerate(locs): val[bairro_de[l["id"]]] += blk["val"][j]
info = {sq: (u or "", p or "", s or "") for sq, u, p, s in Q("""SELECT TRY_CAST(SQ_CANDIDATO AS BIGINT), any_value(NM_URNA_CANDIDATO), any_value(SG_PARTIDO), any_value(DS_SIT_TOT_TURNO)
    FROM v_cand WHERE ano = 2024 AND upper(DS_CARGO) = 'VEREADOR' AND upper(NM_UE) = ? GROUP BY 1""", MUN)}
eleitos = {sq for sq, (u, p, s) in info.items() if s.upper().startswith("ELEITO")}
rows = Q("""SELECT TRY_CAST(NR_ZONA AS INT), TRY_CAST(NR_LOCAL_VOTACAO AS INT), TRY_CAST(SQ_CANDIDATO AS BIGINT), sum(COALESCE(TRY_CAST(QT_VOTOS AS BIGINT), 0))
    FROM v_votos_secao WHERE ano = 2024 AND upper(DS_CARGO) = 'VEREADOR' AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ?
      AND TRY_CAST(SQ_CANDIDATO AS BIGINT) > 0 GROUP BY 1, 2, 3""", MUN)
B = collections.defaultdict(collections.Counter); sem_bairro = 0
for z, l, sq, v in rows:
    b = bairro_de.get(f"{z}-{l}")
    if b is None: sem_bairro += int(v or 0); continue
    B[b][sq] += int(v or 0)
tot = collections.Counter()
for c in B.values(): tot.update(c)
nm = lambda sq: f"{info.get(sq, ('?', '?', ''))[0]} ({info.get(sq, ('?', '?', ''))[1]})"
ok_b = [b for b in val if val[b] >= MIN_VAL and B.get(b)]
foco = [s for s in info if any(f in info[s][0].upper() for f in FOCO) and tot[s]]
def secao(t): print("\n" + "=" * 8, t, "=" * 8)
def rodar(t, fn):
    secao(t)
    try: fn()
    except Exception as e: print("   FALHOU:", type(e).__name__, str(e)[:300])
print(f"Barueri 2024, vereador: {len(locs)} locais em {len(val)} bairros | {len(eleitos)} eleitos | votos nominais mapeados {sum(tot.values()):,} (sem bairro: {sem_bairro:,})")
print(f"Bairros com {MIN_VAL:,} votos válidos ou mais: {len(ok_b)} de {len(val)} | acompanhados: {', '.join(info[s][0] for s in foco) or 'nenhum encontrado'}")

def s1():
    linhas = []
    for b in sorted(ok_b, key=lambda x: -val[x]):
        c = B[b]; nom = sum(c.values()) or 1; ordem = c.most_common(); acc = n50 = 0
        for sq, v in ordem:
            acc += v; n50 += 1
            if acc >= 0.5 * nom: break
        (a, v1), (a2, v2) = ordem[0], (ordem[1] if len(ordem) > 1 else (None, 0))
        linhas.append({"bairro": b, "votos válidos": val[b], "1º": nm(a), "% do bairro": 100 * v1 / val[b], "2º": nm(a2) if a2 else "-",
                       "% 2º": 100 * v2 / val[b], "candidatos para 50% dos votos": n50, "concentração (HHI)": 10000 * sum((v / nom) ** 2 for v in c.values())})
    print(pd.DataFrame(linhas).to_string(index=False))
    print("(HHI perto de 0 = votos pulverizados; 10.000 = um só candidato leva tudo. 'Candidatos para 50%' alto indica bairro sem dono.)")

def s2():
    linhas = []
    for sq in sorted(eleitos | set(foco), key=lambda s: -tot[s]):
        v = tot[sq]
        if not v: continue
        por = sorted([(b, B[b].get(sq, 0)) for b in B], key=lambda x: -x[1])
        forte = sorted([(b, 100 * B[b].get(sq, 0) / val[b]) for b in ok_b], key=lambda x: -x[1])[:3]
        linhas.append({"candidato": info[sq][0], "partido": info[sq][1], "votos": v, "eleito": "sim" if sq in eleitos else "não",
                       "bairros em que é o 1º": sum(1 for b in ok_b if B[b].most_common(1)[0][0] == sq),
                       "5 bairros somam (% dos votos dele)": 100 * sum(x for _, x in por[:5]) / v,
                       "mais forte em (% do bairro)": ", ".join(f"{b} {s:.0f}%" for b, s in forte)})
    print(pd.DataFrame(linhas).to_string(index=False))

def s3():
    for sq in foco:
        a = {b: B[b].get(sq, 0) / tot[sq] for b in B}; res = []
        for o in eleitos:
            if o == sq or not tot[o]: continue
            res.append((sum(min(a[b], B[b].get(o, 0) / tot[o]) for b in B), o))
        res.sort(reverse=True)
        print(f"{nm(sq)}: sobreposição com os demais eleitos (100% = mesma distribuição de votos pelos bairros): " + "; ".join(f"{nm(o)} {100 * x:.0f}%" for x, o in res[:5]))

def s4():
    linhas = []
    for b in val:
        if val[b] < 2500 or not B.get(b): continue
        c = B[b]; sq1, v1 = c.most_common(1)[0]
        linhas.append({"bairro": b, "votos válidos": val[b], "líder": nm(sq1), "% do líder": 100 * v1 / val[b], "candidatos com 3% do bairro ou mais": sum(1 for v in c.values() if v >= 0.03 * val[b])})
    print(pd.DataFrame(linhas).sort_values("% do líder").head(10).to_string(index=False))
    print("Bairro disperso não é oportunidade garantida: pode indicar falta de organização local. É ponto de partida para trabalho de campo.")

rodar("1. Bairros: quem lidera, concentração e dispersão", s1)
rodar("2. Cada vereador eleito: onde é forte e quanto se concentra", s2)
rodar("3. Sobreposição territorial dos vereadores acompanhados", s3)
rodar("4. Bairros mais dispersos", s4)
