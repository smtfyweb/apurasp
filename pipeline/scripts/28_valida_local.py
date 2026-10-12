import duckdb, json, pathlib, random
random.seed(7)
con = duckdb.connect("data/apurasp.duckdb", read_only=True)
mapa = json.load(open("public/data/mapa.json", encoding="utf-8"))
ALVOS = [("3534401", "OSASCO"), ("3505708", "BARUERI")]
BLOCOS = [("2024", "vereador1", "VEREADOR", "vereador"), ("2026", "estadual1", "DEPUTADO ESTADUAL", "estadual")]
SQL = """SELECT c.urna, s.v FROM (
           SELECT TRY_CAST(SQ_CANDIDATO AS BIGINT) sq, sum(COALESCE(TRY_CAST(QT_VOTOS AS BIGINT), 0)) v
           FROM v_votos_secao WHERE ano = ? AND upper(DS_CARGO) = ? AND NR_TURNO = '1' AND upper(NM_MUNICIPIO) = ?
             AND TRY_CAST(NR_ZONA AS INT) = ? AND TRY_CAST(NR_LOCAL_VOTACAO AS INT) = ? AND TRY_CAST(SQ_CANDIDATO AS BIGINT) > 0
           GROUP BY 1) s
         LEFT JOIN (SELECT ano, TRY_CAST(SQ_CANDIDATO AS BIGINT) sq, any_value(NM_URNA_CANDIDATO) urna FROM v_cand GROUP BY 1, 2) c ON c.ano = ? AND c.sq = s.sq
         ORDER BY s.v DESC, c.urna LIMIT 5"""
ruim = conferidos = 0
for cod, nome in ALVOS:
    micro = json.load(open(f"public/data/micro/{cod}.json", encoding="utf-8"))
    fp = pathlib.Path(f"public/data/topo/{cod}.json")
    topo = json.load(open(fp, encoding="utf-8"))["t"] if fp.exists() else None
    for ano, chave, cargo, ck in BLOCOS:
        bl = micro["votos"].get(ano, {}).get(chave); locs = micro["locais"].get(ano, [])
        if not bl: print(f"\n{nome} {ano} {ck}: sem bloco no arquivo do mapa"); continue
        tot = sum(bl["val"]); ofc = mapa["m"][cod]["d"][ano][ck]["v"]
        print(f"\n{nome} {ano} {ck}: soma dos locais {tot:,} | total do município {ofc:,} | diferença {tot - ofc:+,}")
        if topo is None: print("   (arquivo topo não encontrado: rode o script 27)"); continue
        blk = topo[ano][chave]
        idx = sorted(range(len(locs)), key=lambda j: -(locs[j].get("el") or 0))
        amostra = idx[:2] + random.sample(idx[2:], min(3, max(0, len(idx) - 2)))
        extra = [j for j in range(len(locs)) if "PENNACINO" in (locs[j].get("n") or "").upper()]
        for j in dict.fromkeys(amostra + extra):
            l = locs[j]; z, lv = l["id"].split("-")
            esperado = [(n, int(v)) for n, v in con.execute(SQL, [int(ano), cargo, nome, int(z), int(lv), int(ano)]).fetchall()]
            site = [(blk["c"][ci][0], v) for ci, v in blk["l"].get(l["id"], [])][:5]
            conferidos += 1
            if [v for _, v in esperado] == [v for _, v in site]:
                print(f"   OK         {(l.get('n') or '')[:34]:<34} {l.get('b') or '':<22} {site[:3]}")
            else:
                ruim += 1
                print(f"   DIFERENTE  {l.get('n')} ({l.get('b')})\n      banco: {esperado}\n      topo:  {site}")
print(f"\nlocais conferidos: {conferidos} | divergências: {ruim}")
