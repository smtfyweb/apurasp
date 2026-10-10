import json, pathlib
OUT = pathlib.Path("public/data")
CATS = ["extrema-esquerda", "esquerda", "centro-esquerda", "centro", "centro-direita", "direita", "extrema-direita"]
res = {}
for f in sorted((OUT / "municipios").glob("*.json")):
    j = json.load(open(f, encoding="utf-8")); d = {}
    for ano, cargos in (j.get("deputados") or {}).items():
        for cargo, v in cargos.items():
            esp = (((j.get("espectro") or {}).get("dados") or {}).get(ano) or {}).get(cargo) or {}
            campo = max(CATS, key=lambda c: esp.get(c) or 0) if esp else None
            if campo and not (esp.get(campo) or 0): campo = None
            d.setdefault(ano, {})[cargo] = {
                "p": [[x["partido"], round(x.get("pct") or 0, 1)] for x in v.get("partidos", [])[:3]],
                "c": [[x["nome"], x["partido"], round(x.get("pct") or 0, 1)] for x in v.get("candidatos", [])[:3]],
                "nota": esp.get("nota_media"), "campo": campo}
    ib = j.get("dados_ibge") or {}
    el = ((j.get("eleitorado") or {}).get("2026") or {}).get("total")
    res[str(j["ibge"])] = {"n": j["nome"], "pop": ib.get("populacao_2022"), "el": el, "d": d}
p = OUT / "mapa.json"
p.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(res), "municípios em mapa.json |", round(p.stat().st_size / 1e6, 2), "MB")
