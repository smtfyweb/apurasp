import json, pathlib, requests

Q = """
SELECT ?ibge ?itemLabel ?flag ?brasao WHERE {
  ?item wdt:P1585 ?ibge .
  FILTER(STRSTARTS(STR(?ibge), "35"))
  OPTIONAL { ?item wdt:P41 ?flag }
  OPTIONAL { ?item wdt:P94 ?brasao }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "pt,en". }
}"""
r = requests.get("https://query.wikidata.org/sparql",
                 params={"query": Q, "format": "json"},
                 headers={"User-Agent": "ApuraSP-pesquisa/0.1"}, timeout=120)
r.raise_for_status()
res = {}
for b in r.json()["results"]["bindings"]:
    cod = b["ibge"]["value"]
    d = res.setdefault(cod, {"ibge": cod, "nome": b["itemLabel"]["value"], "bandeira": None, "brasao": None})
    if "flag" in b:   d["bandeira"] = b["flag"]["value"]
    if "brasao" in b: d["brasao"] = b["brasao"]["value"]
lst = sorted(res.values(), key=lambda x: x["nome"])
pathlib.Path("data/referencias").mkdir(parents=True, exist_ok=True)
pathlib.Path("data/referencias/simbolos_sp.json").write_text(json.dumps(lst, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(lst)} municípios | com bandeira: {sum(1 for x in lst if x['bandeira'])} | com brasão: {sum(1 for x in lst if x['brasao'])}")
for n in ("Osasco", "Barueri"):
    print([x for x in lst if x["nome"] == n])
