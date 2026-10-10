import requests, zipfile, pathlib, duckdb

B = "https://cdn.tse.jus.br/estatistica/sead/odsele"
DATASETS = ("votacao_candidato_munzona", "votacao_partido_munzona", "detalhe_votacao_munzona")
TMP = pathlib.Path("pipeline/raw/_tmp"); TMP.mkdir(parents=True, exist_ok=True)
for a in (2022, 2026):
    for d in DATASETS:
        out = pathlib.Path(f"data/parquet/{d}/{d}_{a}_BRASIL.parquet")
        if out.exists():
            print("já existe:", out.name); continue
        zp = TMP / f"{d}_{a}.zip"
        print("↓", f"{d}_{a}.zip")
        with requests.get(f"{B}/{d}/{d}_{a}.zip", stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(zp, "wb") as fh:
                for ch in r.iter_content(1 << 20): fh.write(ch)
        z = zipfile.ZipFile(zp)
        br = [n for n in z.namelist() if n.upper().endswith("_BRASIL.CSV")]
        if not br:
            print("   sem arquivo BRASIL no zip. Arquivos:", z.namelist()[:6]); zp.unlink(); continue
        z.extract(br[0], TMP); f = TMP / br[0]
        out.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect()
        for opc in ("", ", strict_mode=false"):
            try:
                rel = f"read_csv('{f}', delim=';', header=true, all_varchar=true, encoding='latin-1'{opc})"
                con.execute(f"COPY (SELECT * FROM {rel} WHERE SG_UF='SP' AND upper(DS_CARGO)='PRESIDENTE') "
                            f"TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
                break
            except Exception as e:
                print("   aviso:", str(e)[:140])
        if out.exists():
            n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
            print(f"   {out.name}: {n:,} linhas")
        f.unlink(); zp.unlink()
print("Concluído.")
