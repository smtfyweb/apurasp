import requests, json, pathlib
B = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/35?intrarregiao=municipio&formato=application/vnd.geo+json&qualidade="
j = None
for q in ("intermediaria", "minima"):
    try:
        r = requests.get(B + q, timeout=300); r.raise_for_status(); j = r.json()
        print("qualidade", q, "|", round(len(r.content) / 1e6, 1), "MB"); break
    except Exception as e:
        print("falhou", q, str(e)[:120])
if not j: raise SystemExit("Não consegui baixar a malha municipal.")
arred = lambda c: [round(c[0], 5), round(c[1], 5)] if isinstance(c[0], (int, float)) else [arred(x) for x in c]
OUT = pathlib.Path("public/data/geo/mun"); OUT.mkdir(parents=True, exist_ok=True); tam = 0
for f in j["features"]:
    g = f["geometry"]; p = OUT / f"{f['properties']['codarea']}.json"
    p.write_text(json.dumps({"type": g["type"], "coordinates": arred(g["coordinates"])}, separators=(",", ":")), encoding="utf-8")
    tam += p.stat().st_size
print(len(j["features"]), "contornos de município |", round(tam / 1e6, 1), "MB")
