import os
import json, pathlib, re, html, time, urllib.parse, csv, io, collections, requests
from PIL import Image

UA = {"User-Agent": "ApuraSP/0.1 (projeto de pesquisa eleitoral; contato: " + os.environ.get("APURASP_CONTATO", "nao informado") + ")"}
API = "https://commons.wikimedia.org/w/api.php"
LARG_API = 250   # largura padrão do Wikimedia: tamanhos fora da lista padrão são limitados (HTTP 429)
LARG = 160       # largura final salva no site
OUT = pathlib.Path("public/img/simbolos"); OUT.mkdir(parents=True, exist_ok=True)

S = requests.Session(); S.headers.update(UA)
nomes = {m["ibge"]: m["nome"] for m in json.load(open("public/data/municipios.json", encoding="utf-8"))}
itens = []
for x in json.load(open("data/referencias/simbolos_sp.json", encoding="utf-8")):
    for tipo in ("bandeira", "brasao"):
        u = x.get(tipo)
        if u and "Special:FilePath/" in u:
            arq = urllib.parse.unquote(u.split("Special:FilePath/", 1)[1]).replace("_", " ")
            itens.append((x["ibge"], tipo, "File:" + arq))
print(len(itens), "imagens para consultar")

def val(em, k):
    v = (em.get(k) or {}).get("value")
    return html.unescape(re.sub(r"<[^>]+>", "", v)).strip() if isinstance(v, str) else ""

def classe(em):
    lic = val(em, "LicenseShortName"); low = lic.lower()
    if not lic: return "verificar", "sem informação de licença"
    if set(re.findall(r"[a-z0-9]+", low)) & {"nc", "nd", "fair", "noncommercial"}: return "bloqueada", lic
    if low.startswith(("public domain", "pd", "cc0", "cc by")) or val(em, "Copyrighted").lower() == "false": return "livre", lic
    return "verificar", lic

def consulta(titulos):
    for t in range(5):
        r = S.get(API, params={"action": "query", "format": "json", "formatversion": "2", "redirects": "1", "prop": "imageinfo",
                               "iiprop": "url|mime|extmetadata", "iiurlwidth": LARG_API, "titles": "|".join(titulos)}, timeout=90)
        if r.status_code in (429, 503): time.sleep(5 * (t + 1)); continue
        r.raise_for_status(); return r.json().get("query", {})
    return {}

def baixar(url):
    ultimo = "sem resposta"
    for t in range(6):
        r = S.get(url, timeout=60)
        tipo = r.headers.get("content-type", "").split(";")[0]
        if r.status_code == 200 and tipo.startswith("image/"):
            return r.content
        ultimo = f"HTTP {r.status_code} {tipo}"
        try: espera = int(r.headers.get("Retry-After", "0"))
        except ValueError: espera = 0
        time.sleep(max(espera, 4 * (t + 1)))
    raise RuntimeError(ultimo)

info = {}
for i in range(0, len(itens), 40):
    lote = itens[i:i + 40]
    q = consulta([t for _, _, t in lote])
    alias = {n["from"]: n["to"] for n in q.get("normalized", [])}
    alias.update({n["from"]: n["to"] for n in q.get("redirects", [])})
    paginas = {p["title"]: p for p in q.get("pages", [])}
    for ibge, tipo, t in lote:
        x = t
        for _ in range(3): x = alias.get(x, x)
        info[(ibge, tipo)] = (t, paginas.get(x))
    time.sleep(0.2)
print("licenças consultadas:", len(info))

saida, linhas, feitas = {}, [], 0
cont, licencas, motivos = collections.Counter(), collections.Counter(), collections.Counter()
for (ibge, tipo), (t, p) in info.items():
    ii = (p or {}).get("imageinfo") or []
    if not p or p.get("missing") or not ii:
        cont["arquivo não encontrado"] += 1; linhas.append([ibge, nomes.get(ibge, ""), tipo, t, "ausente", "", "", ""])
        continue
    em = ii[0].get("extmetadata") or {}
    c, lic = classe(em); autor = val(em, "Artist")[:160]
    pagina = "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_"))
    licencas[(c, lic)] += 1
    if c == "livre":
        destino = OUT / f"{ibge}-{tipo}.webp"
        try:
            if not destino.exists():
                url = ii[0].get("thumburl")
                if not url: raise RuntimeError("sem miniatura (formato sem pré-visualização)")
                im = Image.open(io.BytesIO(baixar(url))).convert("RGBA"); im.thumbnail((LARG, LARG * 2))
                im.save(destino, "WEBP", quality=82, method=6)
                time.sleep(0.5)
            saida.setdefault(ibge, {})[tipo] = {"arquivo": destino.name, "autor": autor, "licenca": lic, "pagina": pagina}
        except Exception as e:
            c = "erro ao baixar"; motivos[str(e)[:90]] += 1
            print("   erro:", ibge, tipo, str(e)[:90])
    cont[c] += 1; linhas.append([ibge, nomes.get(ibge, ""), tipo, p["title"], c, lic, autor, pagina])
    feitas += 1
    if feitas % 100 == 0: print(f"   {feitas}/{len(info)}")

pathlib.Path("public/data/simbolos.json").write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
with open("docs/simbolos_licencas.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, delimiter=";"); w.writerow(["ibge", "municipio", "tipo", "arquivo_commons", "situacao", "licenca", "autor", "pagina"]); w.writerows(linhas)
tam = sum(f.stat().st_size for f in OUT.glob("*")) / 1e6
print("\nSituação:", dict(cont))
print(f"Imagens salvas: {sum(len(v) for v in saida.values())} em {len(saida)} municípios | {tam:.1f} MB em public/img/simbolos")
print("Licenças mais comuns:", [(f"{c}: {l}", n) for (c, l), n in licencas.most_common(10)])
if motivos: print("Motivos das falhas:", dict(motivos))
print("Sem nenhuma imagem livre:", [nomes.get(i, i) for i in nomes if i not in saida][:12], "...")
