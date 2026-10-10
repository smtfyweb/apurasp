import json, re, pathlib

UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
ALVO = [
 "candidatos-2022","candidatos-2024","candidatos-2026",
 "eleitorado-2022","eleitorado-2024","eleitorado-2026",
 "resultados-2022","resultados-2024","resultados-2026",
 "comparecimento-e-abstencao-2022","comparecimento-e-abstencao-2024",
 "dadosabertos-tse-jus-br-dataset-prestacao-de-contas-eleitorais-2022",
 "prestacao-de-contas-eleitorais-2024","prestacao-de-contas-eleitorais-2026",
 "codigos-oficiais-de-uf-e-municipios-segundo-o-tse-e-o-ibge",
 "rae-requerimento-de-alistamento-eleitoral","transferencia-do-eleitorado",
]
cat = {d["id"]: d for d in json.load(open("docs/catalogo_tse.json", encoding="utf-8"))}
out = []
for i in ALVO:
    d = cat.get(i)
    if not d:
        out.append(f"## {i}: NÃO ENCONTRADO\n"); continue
    out.append(f"## {i}  ({d['titulo']}) atualizado {(d['atualizado'] or '')[:10]}")
    mantidos = 0
    for r in d["recursos"]:
        base = (r["url"] or "").split("/")[-1]
        toks = {t.upper() for t in re.split(r"[_\-\s.]", base) if len(t) == 2}
        outras = (toks & UFS) - {"SP"}
        if outras:
            continue
        mantidos += 1
        mb = f"{int(r['tamanho'])/1e6:.1f}MB" if str(r.get("tamanho") or "").isdigit() else "?"
        out.append(f"- {mb:>8} | {r['nome']} | {r['url']}")
    out.append(f"  ({mantidos} de {len(d['recursos'])} arquivos mantidos)\n")
pathlib.Path("docs/recursos_sp.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
