import duckdb, json, pathlib, re, collections

con = duckdb.connect("data/apurasp.duckdb", read_only=True)
OUT = pathlib.Path("public/data/perfil"); OUT.mkdir(parents=True, exist_ok=True)
ibge = {int(t): str(i) for t, i in con.execute("""SELECT CD_MUNICIPIO_TSE, CD_MUNICIPIO_IBGE
    FROM read_parquet('data/parquet/municipio_tse_ibge/municipio_tse_ibge.parquet') WHERE SG_UF='SP'""").fetchall()}
ORDEM_ESC = ['ANALFABETO', 'LÊ E ESCREVE', 'ENSINO FUNDAMENTAL INCOMPLETO', 'ENSINO FUNDAMENTAL COMPLETO',
             'ENSINO MÉDIO INCOMPLETO', 'ENSINO MÉDIO COMPLETO', 'SUPERIOR INCOMPLETO', 'SUPERIOR COMPLETO']
def k_faixa(s):
    m = re.match(r"\s*(\d+)", s or ""); return int(m.group(1)) if m else 999
def k_esc(s):
    u = (s or "").upper(); return ORDEM_ESC.index(u) if u in ORDEM_ESC else 99

dados = collections.defaultdict(list)
for ano, mun, g, f, e, r, q in con.execute("""SELECT ano, CAST(CD_MUNICIPIO AS INT), DS_GENERO, DS_FAIXA_ETARIA,
    DS_GRAU_ESCOLARIDADE, DS_RACA_COR, sum(COALESCE(TRY_CAST(QT_ELEITORES AS BIGINT),0))
    FROM v_perfil_mun WHERE ano IN (2022, 2026) GROUP BY ALL""").fetchall():
    if q and mun in ibge: dados[(mun, ano)].append((g or "NÃO INFORMADO", f or "Inválida", e or "NÃO INFORMADO", r or "NÃO INFORMADO", q))

por_mun = collections.defaultdict(dict)
for (mun, ano), rows in dados.items():
    tot_raca = collections.Counter()
    for g, f, e, r, q in rows: tot_raca[r] += q
    dims = {"genero": sorted({r[0] for r in rows}),
            "faixa": sorted({r[1] for r in rows}, key=k_faixa),
            "escolaridade": sorted({r[2] for r in rows}, key=k_esc),
            "raca": [r for r, _ in tot_raca.most_common()]}
    ix = {d: {v: i for i, v in enumerate(vs)} for d, vs in dims.items()}
    linhas = [[ix["genero"][g], ix["faixa"][f], ix["escolaridade"][e], ix["raca"][r], q] for g, f, e, r, q in rows]
    por_mun[mun][str(ano)] = {"total": sum(r[4] for r in rows), "dims": dims, "linhas": linhas}
tam = 0
for mun, d in por_mun.items():
    p = OUT / f"{ibge[mun]}.json"
    p.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"); tam += p.stat().st_size
print(len(por_mun), "municípios |", round(tam / 1e6, 1), "MB no total")
o = json.load(open(OUT / "3534401.json", encoding="utf-8"))["2026"]
print("Osasco 2026: total", o["total"], "| linhas", len(o["linhas"]), "| dims", {k: len(v) for k, v in o["dims"].items()})
print("faixas:", o["dims"]["faixa"][:4], "...", o["dims"]["faixa"][-3:])
