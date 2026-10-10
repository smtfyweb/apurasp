import csv, json, pathlib, unicodedata
def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s.upper() if c.isalnum() and unicodedata.category(c) != "Mn")
out = {}
for r in csv.DictReader(open("data/referencias/espectro_partidos.csv", encoding="utf-8")):
    cat = (r.get("espectro") or "").strip()
    if not cat: continue
    n = (r.get("nota_0a10") or "").strip()
    out[norm(r["sigla"])] = [float(n) if n else None, cat]
pathlib.Path("public/data/partidos.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(out), "partidos com classificação em public/data/partidos.json")
