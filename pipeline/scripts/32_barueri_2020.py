import requests, zipfile, pathlib, duckdb, glob

B = "https://cdn.tse.jus.br/estatistica/sead/odsele"
ALVO = "BARUERI"
RAW = pathlib.Path("pipeline/raw"); TMP = RAW / "_tmp"; TMP.mkdir(parents=True, exist_ok=True)
PQ = pathlib.Path("data/parquet")
ITENS = [("votacao_candidato_munzona", "votacao_candidato_munzona_2020"), ("votacao_partido_munzona", "votacao_partido_munzona_2020"),
         ("detalhe_votacao_munzona", "detalhe_votacao_munzona_2020"), ("consulta_cand", "consulta_cand_2020"),
         ("consulta_vagas", "consulta_vagas_2020"), ("perfil_eleitorado", "perfil_eleitorado_2020"),
         ("perfil_comparecimento_abstencao", "perfil_comparecimento_abstencao_2022"),
         ("perfil_comparecimento_abstencao", "perfil_comparecimento_abstencao_2024")]

def baixar(url, dest):
    part = dest.with_suffix(".part"); pos = part.stat().st_size if part.exists() else 0
    with requests.get(url, headers={"Range": f"bytes={pos}-"} if pos else {}, stream=True, timeout=120) as r:
        if r.status_code == 404: return False
        if r.status_code == 416: part.rename(dest); return True
        r.raise_for_status()
        with open(part, "ab" if r.status_code == 206 else "wb") as fh:
            for ch in r.iter_content(1 << 20): fh.write(ch)
    part.rename(dest); return True

for pasta, stem in ITENS:
    out = PQ / pasta / f"{stem}_BARUERI.parquet"
    if out.exists(): print("já existe:", out.name); continue
    zp = RAW / f"{stem}.zip"; print("↓", stem)
    try:
        if not baixar(f"{B}/{pasta}/{stem}.zip", zp): print("   não existe no servidor (404)"); continue
    except Exception as e:
        print("   falhou o download:", str(e)[:120]); continue
    z = zipfile.ZipFile(zp); csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
    sp = [n for n in csvs if n.upper().endswith("_SP.CSV")]; br = [n for n in csvs if n.upper().endswith("_BRASIL.CSV")]
    alvo = (sp or br or csvs or [None])[0]
    if not alvo: print("   zip sem CSV:", z.namelist()[:5]); zp.unlink(); continue
    z.extract(alvo, TMP); f = TMP / alvo; out.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(); feito = False
    for opc in ("", ", strict_mode=false"):
        try:
            rel = f"read_csv('{f}', delim=';', header=true, all_varchar=true, encoding='latin-1'{opc})"
            cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {rel}").fetchall()]
            col = next((c for c in ("NM_MUNICIPIO", "NM_UE") if c in cols), None)
            if not col: print("   sem coluna de município. Colunas:", cols[:15]); break
            uf = " AND SG_UF = 'SP'" if "SG_UF" in cols else ""
            con.execute(f"COPY (SELECT * FROM {rel} WHERE upper({col}) = '{ALVO}'{uf}) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            feito = True; break
        except Exception as e:
            print(f"   aviso ({'padrão' if not opc else 'tolerante'}): {str(e)[:120]}")
    f.unlink(missing_ok=True); zp.unlink(missing_ok=True)
    if feito:
        n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
        print(f"   {out.name}: {n:,} linhas | {out.stat().st_size / 1e6:.1f} MB" + ("  ATENÇÃO: nenhuma linha de Barueri" if n == 0 else ""))

print("\nlimpeza do que não vamos usar (2018 e 2020 do estado inteiro):")
rem = 0
for p in sorted(PQ.rglob("*")):
    if p.is_file() and ("2018" in p.name or ("2020" in p.name and "BARUERI" not in p.name)):
        print("   removendo", p.relative_to(PQ), f"({p.stat().st_size / 1e6:.0f} MB)"); p.unlink(); rem += 1
print("   nada a remover" if not rem else f"   {rem} arquivo(s) removido(s)")

con = duckdb.connect()
cols = lambda f: [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{f}')").fetchall()]
nlin = lambda f: con.execute(f"SELECT count(*) FROM read_parquet('{f}')").fetchone()[0]
print("\n=== 2020 (Barueri) em relação a 2022: colunas que faltam ou sobram ===")
for pasta, stem in ITENS:
    if "comparecimento" in pasta: continue
    f20 = PQ / pasta / f"{stem}_BARUERI.parquet"; ref = sorted(glob.glob(str(PQ / pasta / "*2022*.parquet")))
    if f20.exists() and ref:
        a, b = set(cols(ref[0])), set(cols(f20))
        print(f"{pasta}: {nlin(f20):,} linhas | sem {sorted(a - b)[:12] or '-'} | a mais {sorted(b - a)[:12] or '-'}")
for ano in ("2022", "2024"):
    f = PQ / "perfil_comparecimento_abstencao" / f"perfil_comparecimento_abstencao_{ano}_BARUERI.parquet"
    if f.exists():
        cs = cols(f)
        print(f"\ncomparecimento e abstenção {ano}: {nlin(f):,} linhas | tem seção eleitoral? {any('SECAO' in c for c in cs)}")
        print("   colunas:", ", ".join(cs))
        if ano == "2024": print(con.execute(f"SELECT * FROM read_parquet('{f}') LIMIT 2").fetchdf().T.to_string())
