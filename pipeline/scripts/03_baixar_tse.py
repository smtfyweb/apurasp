import sys, zipfile, pathlib, requests, duckdb

B = "https://cdn.tse.jus.br/estatistica/sead/odsele"
RAW, PQ, LEIAME = pathlib.Path("pipeline/raw"), pathlib.Path("data/parquet"), pathlib.Path("docs/leiame")
TMP = RAW / "_tmp"

ONDA1 = [f"{B}/municipio_tse_ibge/municipio_tse_ibge.zip",
         f"{B}/relatorio_resultado_totalizacao/Relatorio_Resultado_Totalizacao_2026_SP.zip",
         f"{B}/votacao_secao/votacao_secao_2024_SP.zip"]
for a in (2022, 2024, 2026):
    ONDA1 += [f"{B}/consulta_cand/consulta_cand_{a}.zip",
              f"{B}/consulta_vagas/consulta_vagas_{a}.zip",
              f"{B}/perfil_eleitorado/perfil_eleitorado_{a}.zip",
              f"{B}/perfil_eleitor_secao/perfil_eleitor_secao_{a}_SP.zip",
              f"{B}/eleitorado_locais_votacao/eleitorado_local_votacao_{a}.zip"]
for a in (2022, 2024):
    ONDA1 += [f"{B}/votacao_candidato_munzona/votacao_candidato_munzona_{a}.zip",
              f"{B}/votacao_partido_munzona/votacao_partido_munzona_{a}.zip",
              f"{B}/detalhe_votacao_munzona/detalhe_votacao_munzona_{a}.zip"]

ONDA2 = [f"{B}/votacao_secao/votacao_secao_2022_SP.zip"]
for a in (2022, 2024):
    ONDA2 += [f"{B}/perfil_comparecimento_abstencao/perfil_comparecimento_abstencao_{a}.zip",
              f"{B}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{a}.zip"]
for a in (2022, 2024, 2026):
    ONDA2.append(f"{B}/bem_candidato/bem_candidato_{a}.zip")

onda = sys.argv[1] if len(sys.argv) > 1 else "1"
ONDA3 = [f"{B}/votacao_candidato_munzona/votacao_candidato_munzona_2026.zip",
         f"{B}/votacao_partido_munzona/votacao_partido_munzona_2026.zip",
         f"{B}/detalhe_votacao_munzona/detalhe_votacao_munzona_2026.zip"]
ONDA4 = [f"{B}/votacao_secao/votacao_secao_2022_SP.zip", f"{B}/votacao_secao/votacao_secao_2026_SP.zip"]
urls = {"1": ONDA1, "2": ONDA2, "3": ONDA3, "4": ONDA4}[onda]
s = requests.Session(); s.headers["User-Agent"] = "ApuraSP-pesquisa/0.1"

def info(u):
    dataset, stem = u.split("/")[-2], u.split("/")[-1][:-4]
    return dataset, stem, PQ / dataset / f".{stem}.ok"

fila, total = [], 0
for u in urls:
    dataset, stem, ok = info(u)
    if ok.exists():
        print(f"  já feito   | {stem}"); continue
    try:
        h = s.head(u, allow_redirects=True, timeout=30)
        mb, good = int(h.headers.get("Content-Length", 0)) / 1e6, h.status_code == 200
    except Exception:
        mb, good = 0, False
    print(f"  {'OK ' if good else 'ERRO'} {mb:8.1f} MB | {stem}")
    if good: fila.append(u); total += mb
print(f"\nOnda {onda}: {total/1000:.2f} GB compactados")
if not fila or input("Baixar e converter? [s/N] ").strip().lower() != "s":
    sys.exit("Nada feito.")

def converter(zp, dataset, stem):
    z = zipfile.ZipFile(zp)
    nomes = z.namelist()
    for n in nomes:  # dicionários de dados (leiame)
        if n.lower().endswith((".pdf", ".txt", ".md")) and z.getinfo(n).file_size < 5e6:
            d = LEIAME / stem; d.mkdir(parents=True, exist_ok=True); z.extract(n, d)
    csvs = [n for n in nomes if n.lower().endswith(".csv")]
    if not csvs:
        d = RAW / dataset / stem; d.mkdir(parents=True, exist_ok=True); z.extractall(d); return
    sp = [n for n in csvs if n.upper().endswith("_SP.CSV")]
    br = [n for n in csvs if n.upper().endswith("_BRASIL.CSV")]
    for n in (sp or br or csvs):
        TMP.mkdir(parents=True, exist_ok=True); z.extract(n, TMP)
        f = TMP / n
        out = PQ / dataset / (pathlib.Path(n).stem + ".parquet")
        out.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect()
        for opc in ("", ", strict_mode=false"):
            try:
                rel = f"read_csv('{f}', delim=';', header=true, all_varchar=true, encoding='latin-1'{opc})"
                cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {rel}").fetchall()]
                filtro = "WHERE SG_UF = 'SP'" if "SG_UF" in cols and not n.upper().endswith("_SP.CSV") else ""
                con.execute(f"COPY (SELECT * FROM {rel} {filtro}) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
                break
            except Exception as e:
                print(f"   aviso ({'padrão' if not opc else 'tolerante'}): {str(e)[:120]}")
        n_lin = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
        print(f"   {out.name}: {n_lin:,} linhas | {out.stat().st_size/1e6:.0f} MB")
        f.unlink()

for u in fila:
    dataset, stem, ok = info(u)
    zp = RAW / f"{stem}.zip"; part = zp.with_suffix(".part"); RAW.mkdir(parents=True, exist_ok=True)
    pos = part.stat().st_size if part.exists() else 0
    print(f"↓ {stem}")
    with s.get(u, headers={"Range": f"bytes={pos}-"} if pos else {}, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(part, "ab" if r.status_code == 206 else "wb") as fh:
            for ch in r.iter_content(1 << 20): fh.write(ch)
    part.rename(zp)
    converter(zp, dataset, stem)
    zp.unlink(); ok.parent.mkdir(parents=True, exist_ok=True); ok.touch()
print("Concluído. Parquets em data/parquet/ e dicionários em docs/leiame/")
