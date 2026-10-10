import duckdb, json, pathlib, csv, unicodedata, collections

con = duckdb.connect("data/apurasp.duckdb", read_only=True)
Q = lambda sql, *a: con.execute(sql, list(a)).fetchall()
ANOS = {2022: ["PRESIDENTE", "GOVERNADOR", "SENADOR", "DEPUTADO FEDERAL", "DEPUTADO ESTADUAL"],
        2024: ["PREFEITO", "VEREADOR"],
        2026: ["PRESIDENTE", "GOVERNADOR", "SENADOR", "DEPUTADO FEDERAL", "DEPUTADO ESTADUAL"]}
CHAVE = {"PRESIDENTE": "presidente", "GOVERNADOR": "governador", "SENADOR": "senador", "DEPUTADO FEDERAL": "federal",
         "DEPUTADO ESTADUAL": "estadual", "PREFEITO": "prefeito", "VEREADOR": "vereador"}
CATS = ["extrema-esquerda", "esquerda", "centro-esquerda", "centro", "centro-direita", "direita", "extrema-direita"]

def filtro(a=""):
    p = f"{a}." if a else ""
    return "(" + " OR ".join(f"({p}ano={ano} AND upper({p}DS_CARGO) IN ({','.join(repr(c) for c in cs)}))"
                              for ano, cs in ANOS.items()) + ")"
def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s.upper() if c.isalnum() and unicodedata.category(c) != "Mn")

L = {}
for r in csv.DictReader(open("data/referencias/espectro_partidos.csv", encoding="utf-8")):
    if (r.get("espectro") or "").strip():
        n = (r.get("nota_0a10") or "").strip()
        L[norm(r["sigla"])] = (r["espectro"].strip(), float(n) if n else None)
ibge = {int(t): str(i) for t, i in Q("""SELECT CD_MUNICIPIO_TSE, CD_MUNICIPIO_IBGE
    FROM read_parquet('data/parquet/municipio_tse_ibge/municipio_tse_ibge.parquet') WHERE SG_UF='SP'""")}
idx = {x["ibge"]: x for x in json.load(open("public/data/municipios.json", encoding="utf-8"))}

# turno final de cada eleição: 2º turno quando existe, senão o 1º
TF = f"tf AS (SELECT ano, CAST(CD_MUNICIPIO AS INT) mun, upper(DS_CARGO) cargo, max(NR_TURNO) turno FROM v_votos_cand WHERE {filtro()} GROUP BY ALL)"
J = lambda a: f"JOIN tf ON {a}.ano=tf.ano AND CAST({a}.CD_MUNICIPIO AS INT)=tf.mun AND upper({a}.DS_CARGO)=tf.cargo AND {a}.NR_TURNO=tf.turno"
# dedupe por zona (max) antes de somar, para não duplicar linhas que apareçam em mais de um arquivo
A = f"""{TF}, z AS (SELECT c.ano, CAST(c.CD_MUNICIPIO AS INT) mun, upper(c.DS_CARGO) cargo, c.NR_TURNO turno, c.NR_ZONA zona, c.SQ_CANDIDATO sq,
      max(c.NM_URNA_CANDIDATO) nome, max(c.NR_CANDIDATO) num, max(c.SG_PARTIDO) part, max(c.DS_SIT_TOT_TURNO) sit,
      max(COALESCE(TRY_CAST(c.QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT), 0)) v
    FROM v_votos_cand c {J('c')} WHERE {filtro('c')} GROUP BY ALL),
  a AS (SELECT ano, mun, cargo, turno, sq, any_value(nome) nome, any_value(num) num, any_value(part) part,
        any_value(sit) sit, sum(v) v FROM z GROUP BY ALL)"""

cand, turno_de = collections.defaultdict(list), {}
for ano, mun, cargo, turno, nome, num, part, el, v in Q(f"""WITH {A}
    SELECT ano, mun, cargo, turno, nome, num, part, CAST(sit LIKE 'ELEITO%' AS INT), v FROM (
      SELECT *, row_number() OVER (PARTITION BY ano, mun, cargo ORDER BY v DESC) rk FROM a) WHERE rk <= 5
    ORDER BY ano, mun, cargo, v DESC"""):
    k = (ano, mun, CHAVE[cargo]); cand[k].append((nome, num, part, int(el or 0), v or 0)); turno_de[k] = turno

party = collections.defaultdict(lambda: collections.defaultdict(int))
for ano, mun, cargo, part, v in Q(f"WITH {A} SELECT ano, mun, cargo, part, sum(v) FROM a GROUP BY ALL"):
    if part: party[(ano, mun, CHAVE[cargo])][part] += v or 0
for ano, mun, cargo, part, v in Q(f"""WITH {TF}, z AS (SELECT p.ano, CAST(p.CD_MUNICIPIO AS INT) mun, upper(p.DS_CARGO) cargo,
      p.NR_ZONA zona, p.SG_PARTIDO part, max(COALESCE(TRY_CAST(p.QT_VOTOS_LEGENDA_VALIDOS AS BIGINT), 0)) v
    FROM v_votos_partido p {J('p')} WHERE {filtro('p')} GROUP BY ALL)
    SELECT ano, mun, cargo, part, sum(v) FROM z GROUP BY ALL"""):
    if part: party[(ano, mun, CHAVE[cargo])][part] += v or 0

validos = {}
for ano, mun, cargo, v in Q(f"""WITH {TF}, z AS (SELECT d.ano, CAST(d.CD_MUNICIPIO AS INT) mun, upper(d.DS_CARGO) cargo, d.NR_ZONA zona,
      max(COALESCE(TRY_CAST(d.QT_TOTAL_VOTOS_VALIDOS AS BIGINT), 0)) v
    FROM v_detalhe d {J('d')} WHERE {filtro('d')} GROUP BY ALL)
    SELECT ano, mun, cargo, sum(v) FROM z GROUP BY ALL"""):
    validos[(ano, mun, CHAVE[cargo])] = v

seats = collections.defaultdict(dict)
for ano, mun, part, n in Q("""WITH z AS (SELECT c.ano, CAST(c.CD_MUNICIPIO AS INT) mun, c.SQ_CANDIDATO sq, max(c.SG_PARTIDO) part, max(c.DS_SIT_TOT_TURNO) sit
      FROM v_votos_cand c WHERE c.ano=2024 AND upper(c.DS_CARGO)='VEREADOR' AND c.NR_TURNO='1' GROUP BY ALL)
    SELECT ano, mun, part, count(*) FROM z WHERE sit LIKE 'ELEITO%' GROUP BY ALL"""):
    seats[(ano, mun)][part] = n

cand_estado = collections.defaultdict(list)
for ano, cargo, nome, num, part, el, v in Q(f"""WITH {A}
    SELECT ano, cargo, nome, num, part, el, v FROM (
      SELECT ano, cargo, sq, any_value(nome) nome, any_value(num) num, any_value(part) part,
             max(CAST(sit LIKE 'ELEITO%' AS INT)) el, sum(v) v,
             row_number() OVER (PARTITION BY ano, cargo ORDER BY sum(v) DESC) rk
      FROM a GROUP BY ano, cargo, sq) WHERE rk <= 5 ORDER BY ano, cargo, v DESC"""):
    cand_estado[(ano, CHAVE[cargo])].append((nome, num, part, int(el or 0), v or 0))

def bloco(partidos, cands, val, turno, st=None, w=None):
    tot = sum(partidos.values())
    if not tot: return None
    cats, soma, nn = collections.Counter(), 0.0, 0
    for p, v in partidos.items():
        c, n = L.get(norm(p), (None, None))
        cats[c or "sem classificação"] += v
        if n is not None: soma += n * v; nn += v
    den = val or tot
    top = sorted(partidos.items(), key=lambda x: -x[1])[:5]
    if st: w = max(st, key=lambda p: (st[p], partidos.get(p, 0)))
    out = {"v": val, "t": turno, "w": w or (top[0][0] if top else None),
           "nota": round(soma / nn, 2) if nn else None,
           "e": [round(100 * cats.get(c, 0) / tot, 1) for c in CATS + ["sem classificação"]],
           "c": [[n_, num, p, v, round(100 * v / den, 1), el] for n_, num, p, el, v in cands],
           "p": [[p, v, round(100 * v / den, 1)] for p, v in top]}
    if st: out["s"] = sorted(st.items(), key=lambda x: -x[1])[:5]; out["cad"] = sum(st.values())
    return out

res = {"estado": {}, "m": {}}
sp = collections.defaultdict(lambda: collections.defaultdict(int)); sv = collections.Counter()
sseats = collections.defaultdict(lambda: collections.defaultdict(int))
for (ano, mun, cargo), d in party.items():
    if mun not in ibge: continue
    for p, v in d.items(): sp[(ano, cargo)][p] += v
    sv[(ano, cargo)] += validos.get((ano, mun, cargo), 0)
    cod = ibge[mun]; x = idx[cod]
    m = res["m"].setdefault(cod, {"n": x["nome"], "pop": x.get("populacao_2022"), "el": x.get("eleitores_2026"), "d": {}})
    cs = cand.get((ano, mun, cargo), [])
    st = dict(seats[(ano, mun)]) if cargo == "vereador" and (ano, mun) in seats else None
    forc = next((c[2] for c in cs if c[3]), None) if cargo == "prefeito" else None
    b = bloco(d, cs, validos.get((ano, mun, cargo), 0), turno_de.get((ano, mun, cargo)), st, forc)
    if b: m["d"].setdefault(str(ano), {})[cargo] = b
    if st:
        for p, n in st.items(): sseats[ano][p] += n
for (ano, cargo), d in sp.items():
    st = dict(sseats[ano]) if cargo == "vereador" and sseats[ano] else None
    b = bloco(d, cand_estado.get((ano, cargo), []), sv[(ano, cargo)], None, st)
    if b: res["estado"].setdefault(str(ano), {})[cargo] = b

p = pathlib.Path("public/data/mapa.json")
p.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
for cod, m in res["m"].items():                      # a ficha lê os mesmos resultados
    f = pathlib.Path(f"public/data/municipios/{cod}.json")
    if f.exists():
        j = json.load(open(f, encoding="utf-8")); j["resultados"] = m["d"]
        f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")

cont = collections.Counter((a, c) for m in res["m"].values() for a, cs in m["d"].items() for c in cs)
print(round(p.stat().st_size / 1e6, 2), "MB | municípios por eleição e cargo:")
for k in sorted(cont): print("  ", k, cont[k])
seg = collections.Counter((a, c) for m in res["m"].values() for a, cs in m["d"].items() for c, b in cs.items() if b.get("t") == "2")
print("municípios com resultado de 2º turno:", dict(seg))
print("\nEstado, governador 2022 (turno final):", [(c[0], c[3], c[4], c[5]) for c in res["estado"]["2022"]["governador"]["c"][:2]])
print("Estado, vereador 2024, cadeiras por partido:", res["estado"]["2024"]["vereador"].get("s"), "de", res["estado"]["2024"]["vereador"].get("cad"))
for cod in ("3550308", "3534401", "3505708"):
    mm = res["m"][cod]; pr = mm["d"].get("2024", {}).get("prefeito"); ve = mm["d"].get("2024", {}).get("vereador")
    print(f"\n{mm['n']}: prefeito (turno {pr and pr['t']}):", [(c[0], c[2], c[3], c[5]) for c in (pr or {}).get("c", [])[:2]])
    print("   cadeiras:", ve and ve.get("s"), "de", ve and ve.get("cad"), "| vereador mais votado:", ve and (ve["c"][0][0], ve["c"][0][3]))
