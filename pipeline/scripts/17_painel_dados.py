import duckdb, json, pathlib, re, collections

con = duckdb.connect("data/apurasp.duckdb", read_only=True)
OUT = pathlib.Path("public/data/painel"); OUT.mkdir(parents=True, exist_ok=True)
DIMS = ["genero", "faixa", "escolaridade", "estado_civil", "raca"]
COLS = ["DS_GENERO", "DS_FAIXA_ETARIA", "DS_GRAU_ESCOLARIDADE", "DS_ESTADO_CIVIL", "DS_RACA_COR"]
MED = ["QT_ELEITORES", "QT_ELEITORES_BIOMETRIA", "QT_ELEITORES_DEFICIENCIA", "QT_ELEITORES_NOME_SOCIAL"]
existentes = {r[0] for r in con.execute("DESCRIBE SELECT * FROM v_perfil_mun").fetchall()}
faltam = [c for c in COLS + MED if c not in existentes]
if faltam: raise SystemExit(f"Colunas ausentes em v_perfil_mun: {faltam}")

ibge = {int(t): str(i) for t, i in con.execute("""SELECT CD_MUNICIPIO_TSE, CD_MUNICIPIO_IBGE
    FROM read_parquet('data/parquet/municipio_tse_ibge/municipio_tse_ibge.parquet') WHERE SG_UF='SP'""").fetchall()}
sel = ", ".join(f"COALESCE(NULLIF(trim({c}), ''), 'NÃO INFORMADO')" for c in COLS)
soma = lambda c: f"sum(COALESCE(TRY_CAST({c} AS BIGINT), 0))"
rows = con.execute(f"""SELECT ano, CAST(CD_MUNICIPIO AS INT), {sel}, {', '.join(soma(c) for c in MED)}
    FROM v_perfil_mun WHERE ano IN (2022, 2024, 2026) GROUP BY ALL""").fetchall()

ORDEM_ESC = ['ANALFABETO', 'LÊ E ESCREVE', 'ENSINO FUNDAMENTAL INCOMPLETO', 'ENSINO FUNDAMENTAL COMPLETO',
             'ENSINO MÉDIO INCOMPLETO', 'ENSINO MÉDIO COMPLETO', 'SUPERIOR INCOMPLETO', 'SUPERIOR COMPLETO']
ORDEM_EC = ['SOLTEIRO', 'CASADO', 'DIVORCIADO', 'SEPARADO JUDICIALMENTE', 'VIÚVO']
def k_faixa(s):
    m = re.match(r"\s*(\d+)", s); return (int(m.group(1)) if m else 999, s)
def k_esc(s): u = s.upper(); return (ORDEM_ESC.index(u) if u in ORDEM_ESC else 99, s)
def k_ec(s): u = s.upper(); return (ORDEM_EC.index(u) if u in ORDEM_EC else 99, s)

por_ano = collections.defaultdict(list)
for ano, mun, g, f, e, s, r, q, bio, defi, ns in rows:
    if q: por_ano[ano].append((mun, [g, f, e, s, r], q, bio, defi, ns))

dims = {}
for ano, lst in por_ano.items():
    cont = [collections.Counter() for _ in DIMS]
    for _, cats, q, *_ in lst:
        for i, c in enumerate(cats): cont[i][c] += q
    dims[str(ano)] = {"genero": [k for k, _ in cont[0].most_common()],
                      "faixa": sorted(cont[1], key=k_faixa),
                      "escolaridade": sorted(cont[2], key=k_esc),
                      "estado_civil": sorted(cont[3], key=k_ec),
                      "raca": [k for k, _ in cont[4].most_common()]}

PARES = [(i, j) for i in range(len(DIMS)) for j in range(i + 1, len(DIMS))]
def novo(dm):
    m = {d: [0] * len(dm[d]) for d in DIMS}
    for i, j in PARES: m[f"{DIMS[i]}|{DIMS[j]}"] = [0] * (len(dm[DIMS[i]]) * len(dm[DIMS[j]]))
    return {"t": 0, "b": 0, "d": 0, "ns": 0, "m": m}
def somar(a, ix, dm, q, bio, defi, ns):
    a["t"] += q; a["b"] += bio; a["d"] += defi; a["ns"] += ns
    for k, d in enumerate(DIMS): a["m"][d][ix[k]] += q
    for i, j in PARES: a["m"][f"{DIMS[i]}|{DIMS[j]}"][ix[i] * len(dm[DIMS[j]]) + ix[j]] += q

res = collections.defaultdict(dict); est = {}
for ano, lst in por_ano.items():
    dm = dims[str(ano)]; idx = [{c: n for n, c in enumerate(dm[d])} for d in DIMS]
    acc_m, acc_e = {}, novo(dm)
    for mun, cats, q, bio, defi, ns in lst:
        ix = [idx[k][c] for k, c in enumerate(cats)]
        somar(acc_m.setdefault(mun, novo(dm)), ix, dm, q, bio, defi, ns)
        somar(acc_e, ix, dm, q, bio, defi, ns)
    est[str(ano)] = acc_e
    for mun, a in acc_m.items(): res[mun][str(ano)] = a

dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
tam = 0
for mun, d in res.items():
    if mun in ibge:
        p = OUT / f"{ibge[mun]}.json"; p.write_text(dump(d), encoding="utf-8"); tam += p.stat().st_size
(OUT / "estado.json").write_text(dump(est), encoding="utf-8")
(OUT / "dims.json").write_text(dump(dims), encoding="utf-8")
print(len([m for m in res if m in ibge]), "municípios |", round(tam / 1e6, 1), "MB")
for ano in sorted(est):
    dm = dims[ano]; ni = dm["raca"].index("NÃO INFORMADO") if "NÃO INFORMADO" in dm["raca"] else None
    pni = 100 * est[ano]["m"]["raca"][ni] / est[ano]["t"] if ni is not None else 0
    print(f"{ano}: estado {est[ano]['t']:,} eleitores | faixas {len(dm['faixa'])} | raça não informada {pni:.1f}%")
print("Osasco 2026:", res[[k for k, v in ibge.items() if v == '3534401'][0]]["2026"]["t"], "(esperado 583505)")
print("Barueri 2026:", res[[k for k, v in ibge.items() if v == '3505708'][0]]["2026"]["t"], "(esperado 297546)")
