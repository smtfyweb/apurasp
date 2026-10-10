import csv, json, pathlib, unicodedata, collections, duckdb

def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s.upper() if c.isalnum() and unicodedata.category(c) != "Mn")

FONTE = "Bolognesi, Ribeiro, Codato e Silva (2025), Opinião Pública 31:e31120, Tab. 1 (média 2022)"
CATS = ["extrema-esquerda", "esquerda", "centro-esquerda", "centro", "centro-direita", "direita", "extrema-direita"]
SEM = "sem classificação"
T = {  # sigla normalizada: (nota 2022, categoria do artigo, observação)
 "PSTU": (0.51, "extrema-esquerda", ""), "PCO": (0.55, "extrema-esquerda", ""),
 "PCB": (0.69, "extrema-esquerda", ""), "PSOL": (1.41, "extrema-esquerda", ""),
 "UP": (1.63, "esquerda", ""), "PCDOB": (1.78, "esquerda", ""), "PT": (2.68, "esquerda", ""),
 "PSB": (3.59, "centro-esquerda", ""), "REDE": (3.69, "centro-esquerda", ""),
 "PDT": (3.86, "centro-esquerda", ""), "PV": (4.12, "centro-esquerda", ""),
 "SOLIDARIEDADE": (6.01, "centro-direita", "SDD na tabela"), "CIDADANIA": (6.17, "centro-direita", "CDD na tabela"),
 "AVANTE": (6.47, "centro-direita", ""), "MDB": (6.50, "centro-direita", ""),
 "MOBILIZA": (6.74, "centro-direita", "ex-PMN (mudança de nome)"), "PMN": (6.74, "centro-direita", "hoje Mobiliza"),
 "PSDB": (6.76, "centro-direita", ""),
 "PSD": (6.94, "direita", "categoria pela média ponderada do artigo (7,15)"),
 "PMB": (7.29, "direita", ""), "PODE": (7.44, "direita", ""),
 "PROS": (7.45, "direita", "partido extinto/incorporado após 2022"), "PRTB": (7.49, "direita", ""),
 "AGIR": (7.55, "direita", ""), "PTB": (7.72, "direita", "fundido no PRD em 2023"),
 "PP": (8.15, "direita", "PROGRE na tabela"), "DC": (8.21, "direita", ""),
 "REPUBLICANOS": (8.33, "extrema-direita", "categoria pela média ponderada do artigo (8,58)"),
 "PSC": (8.41, "extrema-direita", "partido extinto/incorporado após 2022"),
 "UNIAO": (8.49, "extrema-direita", ""), "PATRIOTA": (8.60, "extrema-direita", "fundido no PRD em 2023"),
 "NOVO": (8.67, "extrema-direita", ""), "PL": (8.80, "extrema-direita", ""),
 "PRD": (8.16, "direita", "DERIVADO: média de PTB e Patriota (regra de fusão do artigo); não medido em survey"),
}
LEGADOS = {"PTB": "PARTIDO TRABALHISTA BRASILEIRO", "PROS": "PARTIDO REPUBLICANO DA ORDEM SOCIAL",
           "PSC": "PARTIDO SOCIAL CRISTÃO", "PATRIOTA": "PATRIOTA", "PMN": "PARTIDO DA MOBILIZAÇÃO NACIONAL"}

# ---------- planilha de espectro (não sobrescreve o que já foi preenchido) ----------
esp = pathlib.Path("data/referencias/espectro_partidos.csv")
rows = {}
if esp.exists():
    for r in csv.DictReader(open(esp, encoding="utf-8")):
        rows[norm(r["sigla"])] = r
for k, nome in LEGADOS.items():
    rows.setdefault(k, {"sigla": k, "nome": nome, "espectro": "", "criterio_fonte": ""})
for k in T:
    rows.setdefault(k, {"sigla": k, "nome": "", "espectro": "", "criterio_fonte": ""})
for k, r in rows.items():
    if (r.get("espectro") or "").strip():
        continue
    if k in T:
        n, cat, obs = T[k]
        r["espectro"], r["nota_0a10"] = cat, f"{n:.2f}"
        r["criterio_fonte"] = FONTE + (f" | {obs}" if obs else "")
    else:
        r["criterio_fonte"] = "NÃO CLASSIFICADO na fonte (partido posterior a 2022 ou ausente do survey)"
with open(esp, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["sigla", "nome", "espectro", "nota_0a10", "criterio_fonte"], extrasaction="ignore")
    w.writeheader()
    for k in sorted(rows): w.writerow({"nota_0a10": "", **rows[k]})
L = {k: (r["espectro"].strip(), float(r["nota_0a10"]) if (r.get("nota_0a10") or "").strip() else None)
     for k, r in rows.items() if (r.get("espectro") or "").strip()}
print(f"{len(L)} partidos classificados; sem classificação: {sorted(r['sigla'] for k, r in rows.items() if k not in L)}")

# ---------- votos por partido, município, ano e cargo ----------
con = duckdb.connect("data/apurasp.duckdb", read_only=True)
CARGOS = {"DEPUTADO FEDERAL": "federal", "DEPUTADO ESTADUAL": "estadual"}
dados = con.execute("""SELECT ano, CAST(CD_MUNICIPIO AS INT), upper(DS_CARGO), SG_PARTIDO,
    sum(COALESCE(TRY_CAST(QT_VOTOS_NOMINAIS_VALIDOS AS BIGINT),0) + COALESCE(TRY_CAST(QT_VOTOS_LEGENDA_VALIDOS AS BIGINT),0))
    FROM v_votos_partido WHERE ano IN (2022, 2026) AND NR_TURNO='1'
      AND upper(DS_CARGO) IN ('DEPUTADO FEDERAL','DEPUTADO ESTADUAL') GROUP BY 1,2,3,4""").fetchall()

agg = collections.defaultdict(collections.Counter)
nota = collections.defaultdict(lambda: [0.0, 0])
sem = collections.defaultdict(collections.Counter)
for ano, mun, cargo, part, v in dados:
    cat, n = L.get(norm(part), (SEM, None))
    for key in ((mun, ano, cargo), (0, ano, cargo)):
        agg[key][cat] += v
        if n is not None: nota[key][0] += n * v; nota[key][1] += v
        if cat == SEM: sem[key][part] += v

def resumo(key):
    tot = sum(agg[key].values())
    if not tot: return None
    d = {c: round(100 * agg[key].get(c, 0) / tot, 2) for c in CATS + [SEM]}
    d["nota_media"] = round(nota[key][0] / nota[key][1], 2) if nota[key][1] else None
    d["votos_partidos"] = tot
    return d

# ---------- grava nos JSONs ----------
ibge = {int(t): str(i) for t, i in con.execute("""SELECT CD_MUNICIPIO_TSE, CD_MUNICIPIO_IBGE
    FROM read_parquet('data/parquet/municipio_tse_ibge/municipio_tse_ibge.parquet') WHERE SG_UF='SP'""").fetchall()}
def bloco(mun):
    e = {}
    for ano in (2022, 2026):
        for cargo, ch in CARGOS.items():
            r = resumo((mun, ano, cargo))
            if r: e.setdefault(str(ano), {})[ch] = r
    return {"fonte": FONTE, "classificacao_de": 2022, "dados": e}
OUT = pathlib.Path("public/data/municipios"); n = 0
for tse, cod in ibge.items():
    f = OUT / f"{cod}.json"
    if f.exists():
        j = json.load(open(f, encoding="utf-8")); j["espectro"] = bloco(tse)
        f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8"); n += 1
pathlib.Path("public/data/estado_sp.json").write_text(json.dumps({"espectro": bloco(0)}, ensure_ascii=False), encoding="utf-8")
print(f"{n} municípios + estado atualizados\n")

# ---------- conferência ----------
inv = {v: k for k, v in ibge.items()}
for nome, mun in (("SP (estado)", 0), ("Osasco", inv["3534401"]), ("Barueri", inv["3505708"])):
    for ano in (2022, 2026):
        for cargo, ch in CARGOS.items():
            r = resumo((mun, ano, cargo))
            if r:
                print(f"{nome:12} {ano} {ch:8} nota {r['nota_media']} | " +
                      ", ".join(f"{c} {r[c]}%" for c in CATS + [SEM] if r[c]))
print("\nMaiores votações SEM classificação no estado:")
for ano in (2022, 2026):
    for cargo, ch in CARGOS.items():
        print(f"  {ano} {ch}:", sem[(0, ano, cargo)].most_common(4))

doc = pathlib.Path("docs/metodologia.md"); txt = doc.read_text(encoding="utf-8") if doc.exists() else ""
if "## Espectro político" not in txt:
    doc.write_text(txt + f"""
## Espectro político
Fonte: {FONTE}. Escala 0–10 de survey de especialistas (2022).
- A classificação é de 2022; os autores não recomendam extrapolá-la para outros anos. Resultados de 2026 são rotulados "classificação de 2022".
- Categorias seguem a média ponderada do artigo; "extrema" é agregação numérica, sem análise da atuação do partido.
- PRD: derivado pela regra de fusão do artigo (média PTB/Patriota). MISSÃO: sem classificação.
- Mobiliza tratado como ex-PMN. Planilha editável em data/referencias/espectro_partidos.csv.
""", encoding="utf-8")
