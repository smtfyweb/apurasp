import requests, json, pathlib, time, collections

S = "https://apisidra.ibge.gov.br/values"
H = {"User-Agent": "ApuraSP-pesquisa/0.1"}
FONTE = "IBGE (SIDRA tabelas 4709, 4714, 5938; API de localidades)"

def sidra(tabela):
    u = f"{S}/t/{tabela}/n6/in%20n3%2035/v/all/p/last"
    err = None
    for i in range(3):
        try:
            r = requests.get(u, headers=H, timeout=180); r.raise_for_status()
            j = r.json()
            if isinstance(j, list) and len(j) > 1: return j[1:]
            print(f"  tabela {tabela}: sem dados -> {str(j)[:200]}"); return []
        except Exception as e:
            err = e; time.sleep(3 * (i + 1))
    print(f"  FALHOU tabela {tabela}: {err}"); return []

def num(v):
    try: return float(v)
    except Exception: return None

D = {}  # tabela -> cod município -> cod variável -> dict
for t in ("4709", "4714", "5938"):
    rows = sidra(t); D[t] = collections.defaultdict(dict)
    for r in rows:
        D[t][r["D1C"]][r["D2C"]] = {"nome": r["D2N"], "unid": r["MN"], "valor": num(r["V"]), "ano": r["D3N"]}
    print(f"tabela {t}: {len(D[t])} municípios")
    cat = {}
    for m in D[t].values():
        for c, v in m.items(): cat[c] = v["nome"]
    for c, n in sorted(cat.items())[:40]: print(f"    var {c}: {n[:110]}")

def acha(tab, cod, var=None, contem=None):
    for c, v in D[tab].get(cod, {}).items():
        if (var and c == var) or (contem and contem.lower() in v["nome"].lower()): return v
    return None

loc = {str(m["id"]): m for m in requests.get(
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/35/municipios", headers=H, timeout=120).json()}
print(f"localidades: {len(loc)} municípios")

OUT = pathlib.Path("public/data/municipios"); n = 0; pops = {}
for f in OUT.glob("*.json"):
    j = json.load(open(f, encoding="utf-8")); cod = str(j["ibge"])
    pop = acha("4709", cod, var="93") or acha("4714", cod, var="93")
    cresc = acha("4709", cod, var="10605")
    area = acha("4714", cod, contem="Área da unidade territorial")
    dens = acha("4714", cod, contem="Densidade demográfica")
    pib = acha("5938", cod, var="37")
    vab = {}
    for c, v in D["5938"].get(cod, {}).items():
        if v["nome"].lower().startswith("valor adicionado bruto") and v["valor"] is not None:
            vab[v["nome"].replace("Valor adicionado bruto a preços correntes ", "").replace("da ", "").replace("do ", "")[:80]] = v["valor"]
    l = loc.get(cod, {})
    j["dados_ibge"] = {
        "fonte": FONTE,
        "populacao_2022": pop["valor"] if pop else None,
        "crescimento_anual_pct": cresc["valor"] if cresc else None,
        "area_km2": area["valor"] if area else None,
        "densidade_hab_km2": dens["valor"] if dens else None,
        "pib_mil_reais": pib["valor"] if pib else None, "pib_ano": pib["ano"] if pib else None,
        "vab_mil_reais": vab,
        "regiao": {"microrregiao": (l.get("microrregiao") or {}).get("nome"),
                   "mesorregiao": ((l.get("microrregiao") or {}).get("mesorregiao") or {}).get("nome"),
                   "regiao_imediata": (l.get("regiao-imediata") or {}).get("nome"),
                   "regiao_intermediaria": ((l.get("regiao-imediata") or {}).get("regiao-intermediaria") or {}).get("nome")}}
    pops[cod] = pop["valor"] if pop else None
    f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8"); n += 1
print(f"\n{n} municípios atualizados com dados do IBGE")

idx = pathlib.Path("public/data/municipios.json")
lst = json.load(open(idx, encoding="utf-8"))
for x in lst: x["populacao_2022"] = pops.get(x["ibge"])
idx.write_text(json.dumps(lst, ensure_ascii=False), encoding="utf-8")

faltam = {c: [x["nome"] for x in lst if pops.get(x["ibge"]) is None][:8] for c in ("populacao",)}
print("sem população:", faltam["populacao"])
for cod in ("3534401", "3505708"):
    j = json.load(open(OUT / f"{cod}.json", encoding="utf-8"))
    d = j["dados_ibge"]; print("\n", j["nome"], {k: v for k, v in d.items() if k not in ("fonte",)})
