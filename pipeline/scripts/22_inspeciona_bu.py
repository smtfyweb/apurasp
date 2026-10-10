import requests, zipfile, pathlib
URL = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_SP_051020261403.zip"
DEST = pathlib.Path("pipeline/raw/bu2026"); DEST.mkdir(parents=True, exist_ok=True)
zp = DEST / "bweb_1t_SP.zip"
if not zp.exists():
    part = zp.with_suffix(".part"); pos = part.stat().st_size if part.exists() else 0
    print("baixando o boletim de urna (cerca de 1,4 GB)...")
    with requests.get(URL, headers={"Range": f"bytes={pos}-"} if pos else {}, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(part, "ab" if r.status_code == 206 else "wb") as fh:
            for ch in r.iter_content(1 << 20): fh.write(ch)
    part.rename(zp)
z = zipfile.ZipFile(zp); tot = 0
for i in z.infolist():
    print(f"{i.file_size / 1e6:10.1f} MB (compactado {i.compress_size / 1e6:.1f}) | {i.filename}"); tot += i.file_size
print(f"descompactado: {tot / 1e9:.1f} GB")
csvs = [i for i in z.infolist() if i.filename.lower().endswith(".csv")]
if csvs:
    with z.open(csvs[0].filename) as f: linhas = f.read(400000).decode("latin-1", errors="replace").splitlines()
    print("\nCabeçalho:", linhas[0])
    for l in linhas[1:4]: print(l[:600])
