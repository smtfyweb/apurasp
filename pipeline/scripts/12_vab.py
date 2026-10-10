import requests, json, pathlib, collections
S = "https://apisidra.ibge.gov.br/values"
u = f"{S}/t/5938/n6/in%20n3%2035/v/498,513,517,525,6575/p/2021,2022,2023"
r = requests.get(u, headers={"User-Agent": "ApuraSP-pesquisa/0.1"}, timeout=240); r.raise_for_status()
NOME = {"498": "total", "513": "agropecuaria", "517": "industria", "525": "administracao_publica", "6575": "servicos"}
D = collections.defaultdict(lambda: collections.defaultdict(dict))
for x in r.json()[1:]:
    try: v = float(x["V"])
    except ValueError: continue
    if x["D2C"] in NOME: D[x["D1C"]][x["D3N"]][NOME[x["D2C"]]] = v
OUT = pathlib.Path("public/data/municipios"); n = 0; anos = collections.Counter()
for f in OUT.glob("*.json"):
    j = json.load(open(f, encoding="utf-8"))
    ok = [a for a, v in D.get(str(j["ibge"]), {}).items() if len(v) == 5]
    if not ok: continue
    a = max(ok); j.setdefault("dados_ibge", {})["vab"] = {"ano": a, **D[str(j["ibge"])][a]}
    f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8"); n += 1; anos[a] += 1
print(f"VAB por setor em {n} municípios; anos usados: {dict(anos)}")
j = json.load(open(OUT / "3534401.json", encoding="utf-8")); print("Osasco:", j["dados_ibge"].get("vab"))
