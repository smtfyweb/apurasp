import duckdb, json, pathlib, collections, datetime

con = duckdb.connect("data/apurasp.duckdb", read_only=True)
OUT = pathlib.Path("public/data/municipios"); OUT.mkdir(parents=True, exist_ok=True)
Q = lambda sql: con.execute(sql).fetchall()
nz = lambda v: v if v not in (None, "") else "Não informado"

mun = {int(t): {"ibge": str(i), "nome": n} for t, i, n in Q("""
  SELECT CD_MUNICIPIO_TSE, CD_MUNICIPIO_IBGE, NM_MUNICIPIO_IBGE
  FROM read_parquet('data/parquet/municipio_tse_ibge/municipio_tse_ibge.parquet') WHERE SG_UF='SP'""")}
D = {c: {"ibge": m["ibge"], "nome": m["nome"], "eleitorado": {}, "vereanca_2024": None, "prefeito_2024": None}
     for c, m in mun.items()}

# --- eleitorado por ano
for ano, c, tot, fem in Q("""SELECT ano, CAST(CD_MUNICIPIO AS INT), sum(CAST(QT_ELEITORES AS BIGINT)),
    sum(CAST(QT_ELEITORES AS BIGINT)) FILTER (WHERE upper(DS_GENERO)='FEMININO')
    FROM v_perfil_mun GROUP BY 1,2"""):
    if c in D:
        D[c]["eleitorado"][str(ano)] = {"total": tot, "pct_feminino": round(100*(fem or 0)/tot, 1) if tot else None}
for dim, col in (("faixa_etaria", "DS_FAIXA_ETARIA"), ("escolaridade", "DS_GRAU_ESCOLARIDADE"), ("cor_raca", "DS_RACA_COR")):
    for ano, c, k, n in Q(f"""SELECT ano, CAST(CD_MUNICIPIO AS INT), {col}, sum(CAST(QT_ELEITORES AS BIGINT))
                              FROM v_perfil_mun GROUP BY 1,2,3"""):
        if c in D and str(ano) in D[c]["eleitorado"]:
            D[c]["eleitorado"][str(ano)].setdefault(dim, {})[nz(k)] = n

# --- vereança 2024
perf = {sq: (nz(g), nz(r)) for sq, g, r in Q("""SELECT SQ_CANDIDATO, DS_GENERO, DS_COR_RACA FROM v_cand
        WHERE ano=2024 AND upper(DS_CARGO)='VEREADOR'""")}
ver = collections.defaultdict(list)
for c, sq, nome, part, sit, votos in Q("""SELECT CAST(CD_MUNICIPIO AS INT), SQ_CANDIDATO, any_value(NM_URNA_CANDIDATO),
        any_value(SG_PARTIDO), any_value(DS_SIT_TOT_TURNO), sum(CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT))
        FROM v_votos_cand WHERE ano=2024 AND upper(DS_CARGO)='VEREADOR' AND NR_TURNO='1' GROUP BY 1,2"""):
    ver[c].append((sq, nome, part, sit or "", votos or 0))
nd = ("Não informado", "Não informado")
for c, lst in ver.items():
    if c not in D: continue
    el = sorted([x for x in lst if x[3].upper().startswith("ELEITO")], key=lambda x: -x[4])
    D[c]["vereanca_2024"] = {
        "candidatos": len(lst), "votos_nominais": sum(x[4] for x in lst), "cadeiras": len(el),
        "menor_votacao_eleito": el[-1][4] if el else None,
        "eleitos": [{"nome": x[1], "partido": x[2], "votos": x[4]} for x in el],
        "cadeiras_por_partido": dict(collections.Counter(x[2] for x in el).most_common()),
        "perfil_eleitos": {"genero": dict(collections.Counter(perf.get(x[0], nd)[0] for x in el)),
                           "cor_raca": dict(collections.Counter(perf.get(x[0], nd)[1] for x in el))}}

# --- prefeito 2024
pref = collections.defaultdict(list)
for c, turno, nome, part, sit, votos in Q("""SELECT CAST(CD_MUNICIPIO AS INT), NR_TURNO, any_value(NM_URNA_CANDIDATO),
        any_value(SG_PARTIDO), any_value(DS_SIT_TOT_TURNO), sum(CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT))
        FROM v_votos_cand WHERE ano=2024 AND upper(DS_CARGO)='PREFEITO' GROUP BY CD_MUNICIPIO, NR_TURNO, SQ_CANDIDATO"""):
    pref[(c, turno)].append((nome, part, (sit or ""), votos or 0))
for (c, turno), lst in pref.items():
    ven = [x for x in lst if x[2].upper().startswith("ELEITO")]
    if c in D and ven:
        tot = sum(x[3] for x in lst)
        D[c]["prefeito_2024"] = {"nome": ven[0][0], "partido": ven[0][1], "votos": ven[0][3],
                                 "pct_validos": round(100*ven[0][3]/tot, 1) if tot else None, "turno": turno}

# --- símbolos + gravação
simb = {x["ibge"]: x for x in json.load(open("data/referencias/simbolos_sp.json", encoding="utf-8"))}
hoje = datetime.date.today().isoformat(); indice = []
for c, d in D.items():
    s = simb.get(d["ibge"], {})
    d["simbolos"] = {"bandeira": s.get("bandeira"), "brasao": s.get("brasao"), "licenca_conferida": False}
    d["fontes"] = {"dados": "TSE - dadosabertos.tse.jus.br", "gerado_em": hoje}
    (OUT / f"{d['ibge']}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    indice.append({"ibge": d["ibge"], "nome": d["nome"], "eleitores_2026": d["eleitorado"].get("2026", {}).get("total")})
indice.sort(key=lambda x: x["nome"])
pathlib.Path("public/data/municipios.json").write_text(json.dumps(indice, ensure_ascii=False), encoding="utf-8")
print(len(D), "municípios exportados")
for ibge in ("3534401", "3505708"):
    d = json.load(open(OUT / f"{ibge}.json", encoding="utf-8")); v = d["vereanca_2024"] or {}
    print("\n", d["nome"], "| eleitores 2026:", d["eleitorado"].get("2026", {}).get("total"))
    print("  prefeito:", d["prefeito_2024"])
    print("  cadeiras:", v.get("cadeiras_por_partido"))
    print("  perfil eleitos:", v.get("perfil_eleitos"))
