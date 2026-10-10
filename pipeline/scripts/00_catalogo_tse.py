import json, sys, time, pathlib, requests

BASE = "https://dadosabertos.tse.jus.br/api/3/action"
DOCS = pathlib.Path("docs"); DOCS.mkdir(exist_ok=True)
s = requests.Session()
s.headers["User-Agent"] = "ApuraSP-pesquisa/0.1"

def get(action, **params):
    err = None
    for i in range(3):
        try:
            r = s.get(f"{BASE}/{action}", params=params, timeout=60)
            r.raise_for_status()
            j = r.json()
            if j.get("success"):
                return j["result"]
        except Exception as e:
            err = e
            time.sleep(2 * (i + 1))
    print(f"FALHOU {action} {params}: {err}", file=sys.stderr)
    return None

ids = get("package_list")
if not ids:
    sys.exit("Não consegui listar os conjuntos. Me mande o erro acima.")
print(f"{len(ids)} conjuntos encontrados. Baixando metadados...")

catalogo = []
for n, i in enumerate(ids, 1):
    p = get("package_show", id=i)
    if not p:
        continue
    catalogo.append({
        "id": p.get("name"),
        "titulo": p.get("title"),
        "descricao": (p.get("notes") or "")[:400],
        "atualizado": p.get("metadata_modified"),
        "recursos": [
            {"nome": r.get("name"), "formato": r.get("format"),
             "url": r.get("url"), "tamanho": r.get("size")}
            for r in p.get("resources", [])
        ],
    })
    if n % 20 == 0:
        print(f"  {n}/{len(ids)}")
    time.sleep(0.2)

(DOCS / "catalogo_tse.json").write_text(
    json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")

linhas = ["# Catálogo TSE (dados abertos)\n"]
for c in sorted(catalogo, key=lambda x: x["titulo"] or ""):
    fmts = sorted({(r["formato"] or "?") for r in c["recursos"]})
    linhas.append(f"## {c['titulo']}  (`{c['id']}`)")
    linhas.append(f"- atualizado: {c['atualizado']} | arquivos: {len(c['recursos'])} | formatos: {', '.join(fmts)}")
    if c["descricao"]:
        linhas.append(f"- {c['descricao'].strip()[:200]}")
    for r in c["recursos"][:2]:
        linhas.append(f"  - {r['nome']}: {r['url']}")
    linhas.append("")
(DOCS / "catalogo_tse.md").write_text("\n".join(linhas), encoding="utf-8")
print(f"Pronto: {len(catalogo)} conjuntos em docs/catalogo_tse.json e docs/catalogo_tse.md")
