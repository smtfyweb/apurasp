import duckdb, json, pathlib, collections, sys, unicodedata, requests

K, K_MICRO, MINV = 60, 15, 30   # território: 60 candidatos por município e cargo; mapa da home: 15
CARGOS = {2024: ["VEREADOR", "PREFEITO"],
          2022: ["DEPUTADO FEDERAL", "DEPUTADO ESTADUAL"],
          2026: ["DEPUTADO FEDERAL", "DEPUTADO ESTADUAL"]}  # majoritários são secundários: para incluí-los, reponha PRESIDENTE, GOVERNADOR e SENADOR
CHAVE = {"VEREADOR": "vereador", "PREFEITO": "prefeito", "PRESIDENTE": "presidente", "GOVERNADOR": "governador",
         "SENADOR": "senador", "DEPUTADO FEDERAL": "federal", "DEPUTADO ESTADUAL": "estadual"}
sem = lambda s: "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").upper().strip()

con = duckdb.connect("data/apurasp.duckdb", read_only=True)
Q = lambda sql, *a: con.execute(sql, list(a)).fetchall()
OUT = pathlib.Path("public/data/territorio"); OUT.mkdir(parents=True, exist_ok=True)
MIC = pathlib.Path("public/data/micro"); MIC.mkdir(parents=True, exist_ok=True)
mun = {int(t): (str(i), n) for t, i, n in Q("""SELECT CD_MUNICIPIO_TSE, CD_MUNICIPIO_IBGE, NM_MUNICIPIO_IBGE
    FROM read_parquet('data/parquet/municipio_tse_ibge/municipio_tse_ibge.parquet') WHERE SG_UF='SP'""")}
if sys.argv[1:]:
    alvo = {sem(a) for a in sys.argv[1:]}
    mun = {k: v for k, v in mun.items() if sem(v[1]) in alvo}
    if not mun: raise SystemExit("Nenhum município encontrado para: " + ", ".join(sys.argv[1:]))
IDS = ",".join(str(k) for k in mun)
print(len(mun), "município(s)")

LAT = "TRY_CAST(replace(NR_LATITUDE, ',', '.') AS DOUBLE)"; LON = "TRY_CAST(replace(NR_LONGITUDE, ',', '.') AS DOUBLE)"
L = collections.defaultdict(dict)
for ano, m, z, l, nome, end, bai, cep, la, lo, sec, el in Q(f"""
    SELECT ano, TRY_CAST(CD_MUNICIPIO AS INT), TRY_CAST(NR_ZONA AS INT), TRY_CAST(NR_LOCAL_VOTACAO AS INT),
           any_value(NM_LOCAL_VOTACAO), any_value(DS_ENDERECO), any_value(NM_BAIRRO), any_value(NR_CEP),
           avg({LAT}) FILTER (WHERE {LAT} BETWEEN -26 AND -19), avg({LON}) FILTER (WHERE {LON} BETWEEN -54 AND -44),
           count(DISTINCT NR_SECAO), sum(COALESCE(TRY_CAST(QT_ELEITOR_SECAO AS BIGINT), 0))
    FROM v_locais WHERE ano IN (2022, 2024, 2026) AND CAST(NR_TURNO AS VARCHAR) = '1' AND TRY_CAST(CD_MUNICIPIO AS INT) IN ({IDS}) GROUP BY 1, 2, 3, 4"""):
    if m in mun and z is not None and l is not None:
        L[(m, ano)][(z, l)] = {"id": f"{z}-{l}", "n": nome, "e": end, "b": (bai or "").strip() or None,
            "c": (cep or "").strip() or None, "la": round(la, 5) if la is not None else None,
            "lo": round(lo, 5) if lo is not None else None, "s": sec, "el": el}
print("locais carregados:", {a: sum(len(v) for (m, x), v in L.items() if x == a) for a in (2022, 2024, 2026)})

for ano, m, z, l, tot, fem, jov, ido, sup, de in Q(f"""
    SELECT ano, m, z, l, sum(q), sum(q) FILTER (WHERE upper(g)='FEMININO'), sum(q) FILTER (WHERE fx BETWEEN 16 AND 24),
           sum(q) FILTER (WHERE fx BETWEEN 60 AND 200), sum(q) FILTER (WHERE upper(esc)='SUPERIOR COMPLETO'), sum(dd)
    FROM (SELECT ano, TRY_CAST(CD_MUNICIPIO AS INT) m, TRY_CAST(NR_ZONA AS INT) z, TRY_CAST(NR_LOCAL_VOTACAO AS INT) l,
                 DS_GENERO g, DS_GRAU_ESCOLARIDADE esc,
                 COALESCE(TRY_CAST(QT_ELEITORES_PERFIL AS BIGINT), TRY_CAST(QT_ELEITORES AS BIGINT), 0) q,
                 COALESCE(TRY_CAST(QT_ELEITORES_DEFICIENCIA AS BIGINT), 0) dd,
                 TRY_CAST(regexp_extract(DS_FAIXA_ETARIA, '(\\d+)', 1) AS INT) fx
          FROM v_perfil_secao WHERE ano IN (2022, 2024, 2026) AND TRY_CAST(CD_MUNICIPIO AS INT) IN ({IDS})) GROUP BY 1, 2, 3, 4"""):
    loc = L.get((m, ano), {}).get((z, l))
    if loc and tot:
        t = tot
        loc.update(pt=tot, f=round(100 * (fem or 0) / t, 1), j=round(100 * (jov or 0) / t, 1),
                   i=round(100 * (ido or 0) / t, 1), u=round(100 * (sup or 0) / t, 1), d=de or 0)

tem_sec = {r[0] for r in Q("SELECT DISTINCT ano FROM v_votos_secao")}
for a, c, n, ns in Q("SELECT ano, upper(DS_CARGO), count(*), count(*) FILTER (WHERE TRY_CAST(SQ_CANDIDATO AS BIGINT) > 0) FROM v_votos_secao GROUP BY 1, 2 ORDER BY 1, 2"):
    print(f"   votos por seção {a} {c}: {n:,} linhas, {ns:,} com candidato identificado")
part = {(a, s): p for a, s, p in Q("SELECT ano, TRY_CAST(SQ_CANDIDATO AS BIGINT), any_value(SG_PARTIDO) FROM v_cand GROUP BY 1, 2")}
V = collections.defaultdict(dict); P = collections.defaultdict(dict)
for ano, cargos in CARGOS.items():
    if ano not in tem_sec:
        print(f"AVISO: votação por seção de {ano} ainda não está no banco; ficam de fora: {', '.join(cargos)}"); continue
    for cargo in cargos:
        for turno in ("1", "2"):
            rot = f"{ano} {CHAVE[cargo]} turno {turno}"
            try:
                rows = Q(f"""WITH b AS (
                      SELECT TRY_CAST(CD_MUNICIPIO AS INT) m, TRY_CAST(NR_ZONA AS INT) z, TRY_CAST(NR_LOCAL_VOTACAO AS INT) l,
                             TRY_CAST(SQ_CANDIDATO AS BIGINT) sq, any_value(NM_VOTAVEL) nome,
                             sum(COALESCE(TRY_CAST(QT_VOTOS AS BIGINT), 0)) v
                      FROM v_votos_secao WHERE ano=? AND upper(DS_CARGO)=? AND NR_TURNO=? AND TRY_CAST(CD_MUNICIPIO AS INT) IN ({IDS})
                      GROUP BY 1, 2, 3, 4),
                    tot AS (SELECT m, sq, any_value(nome) nome, sum(v) tv FROM b WHERE sq > 0 GROUP BY 1, 2),
                    tp AS (SELECT m, sq, nome, tv FROM (SELECT *, row_number() OVER (PARTITION BY m ORDER BY tv DESC) rk FROM tot)
                           WHERE rk <= {K} AND tv >= {MINV})
                    SELECT b.m, b.z, b.l, b.sq, tp.nome, tp.tv, b.v FROM b JOIN tp ON b.m = tp.m AND b.sq = tp.sq""", ano, cargo, turno)
            except Exception as e:
                print(f"   {rot}: ERRO {str(e)[:160]}"); continue
            if not rows:
                print(f"   {rot}: sem linhas no banco"); continue
            val = Q(f"""SELECT TRY_CAST(CD_MUNICIPIO AS INT), TRY_CAST(NR_ZONA AS INT), TRY_CAST(NR_LOCAL_VOTACAO AS INT),
                  sum(COALESCE(TRY_CAST(QT_VOTOS AS BIGINT), 0)) FILTER (WHERE NR_VOTAVEL NOT IN ('95', '96')),
                  sum(COALESCE(TRY_CAST(QT_VOTOS AS BIGINT), 0)) FILTER (WHERE NR_VOTAVEL = '95'),
                  sum(COALESCE(TRY_CAST(QT_VOTOS AS BIGINT), 0)) FILTER (WHERE NR_VOTAVEL = '96')
                  FROM v_votos_secao WHERE ano=? AND upper(DS_CARGO)=? AND NR_TURNO=? AND TRY_CAST(CD_MUNICIPIO AS INT) IN ({IDS})
                  GROUP BY 1, 2, 3""", ano, cargo, turno)
            pr = Q(f"""WITH cp AS (SELECT ano, TRY_CAST(SQ_CANDIDATO AS BIGINT) sq, any_value(SG_PARTIDO) p FROM v_cand GROUP BY 1, 2),
                  np AS (SELECT ano, upper(DS_CARGO) c, TRY_CAST(NR_PARTIDO AS INT) n, any_value(SG_PARTIDO) p FROM v_cand GROUP BY 1, 2, 3)
                SELECT TRY_CAST(s.CD_MUNICIPIO AS INT) m, TRY_CAST(s.NR_ZONA AS INT) z, TRY_CAST(s.NR_LOCAL_VOTACAO AS INT) l,
                       COALESCE(cp.p, np.p) sg, sum(COALESCE(TRY_CAST(s.QT_VOTOS AS BIGINT), 0)) v
                FROM v_votos_secao s
                LEFT JOIN cp ON cp.ano = s.ano AND cp.sq = TRY_CAST(s.SQ_CANDIDATO AS BIGINT)
                LEFT JOIN np ON np.ano = s.ano AND np.c = upper(s.DS_CARGO) AND np.n = TRY_CAST(s.NR_VOTAVEL AS INT)
                            AND length(s.NR_VOTAVEL) = 2 AND s.NR_VOTAVEL NOT IN ('95', '96')
                            AND COALESCE(TRY_CAST(s.SQ_CANDIDATO AS BIGINT), -1) <= 0
                WHERE s.ano=? AND upper(s.DS_CARGO)=? AND s.NR_TURNO=? AND TRY_CAST(s.CD_MUNICIPIO AS INT) IN ({IDS})
                GROUP BY 1, 2, 3, 4""", ano, cargo, turno)
            por_m = collections.defaultdict(lambda: {"c": {}, "cel": collections.defaultdict(dict)})
            for m, z, l, sq, nome, tv, v in rows:
                por_m[m]["c"][sq] = (nome, tv); por_m[m]["cel"][sq][(z, l)] = v
            valm = collections.defaultdict(dict)
            for m, z, l, a, br, nu in val: valm[m][(z, l)] = (a or 0, br or 0, nu or 0)
            pm = collections.defaultdict(lambda: collections.defaultdict(dict))
            for m, z, l, sg, v in pr:
                if sg and v: pm[m][sg][(z, l)] = v
            ok = tot_l = n_mun = 0
            for m in set(por_m) | set(valm):
                locs = sorted(L.get((m, ano), {}))
                if not locs: continue
                pos = {k: i for i, k in enumerate(locs)}
                ordem, mat, d = [], [], None
                if m in por_m:
                    d = por_m[m]; ordem = sorted(d["c"], key=lambda sq: -d["c"][sq][1])
                    for sq in ordem:
                        arr = [0] * len(locs)
                        for k, v in d["cel"][sq].items():
                            if k in pos: arr[pos[k]] = v
                        mat.append(arr)
                vv = [[valm[m].get(k, (0, 0, 0))[i] for k in locs] for i in range(3)]
                plist, pmat = [], []
                if m in pm:
                    for sg in sorted(pm[m], key=lambda g: -sum(pm[m][g].values())):
                        arr = [pm[m][sg].get(k, 0) for k in locs]; t = sum(arr)
                        if t > 0: plist.append([sg, t]); pmat.append(arr)
                cands = [[sq, d["c"][sq][0], part.get((ano, sq)), d["c"][sq][1]] for sq in ordem]
                chave = f"{ano}|{CHAVE[cargo]}{turno}"
                V[m][chave] = {"t": turno, "val": vv[0], "br": vv[1], "nu": vv[2], "c": cands, "v": mat}
                P[m][chave] = {"t": turno, "val": vv[0], "p": plist, "pv": pmat}
                ok += sum(1 for k in valm[m] if k in pos); tot_l += len(valm[m]); n_mun += 1
            print(f"   {rot}: {n_mun} municípios | locais com voto casados com o cadastro de locais: {ok:,} de {tot_l:,}")

def agrupa(src, m):
    out = {}
    for chave, b in src.get(m, {}).items():
        a, c = chave.split("|"); out.setdefault(a, {})[c] = b
    return out
dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
tam = {}; tam_m = {}
for m, (cod, nome) in mun.items():
    anos = {str(a): [L[(m, a)][k] for k in sorted(L[(m, a)])] for a in (2022, 2024, 2026) if (m, a) in L}
    if not anos: continue
    p = OUT / f"{cod}.json"
    p.write_text(dump({"ibge": cod, "nome": nome, "locais": anos, "votos": agrupa(V, m)}), encoding="utf-8"); tam[nome] = p.stat().st_size
    campos = ("id", "n", "b", "la", "lo", "s", "el", "pt", "f", "j", "i", "u")
    q = MIC / f"{cod}.json"
    q.write_text(dump({"ibge": cod, "nome": nome, "locais": {a: [{k: x[k] for k in campos if k in x} for x in lst] for a, lst in anos.items()},
                       "votos": agrupa(P, m)}), encoding="utf-8"); tam_m[nome] = q.stat().st_size

print("\n=== Qualidade dos locais de votação ===")
for ano in (2022, 2024, 2026):
    lst = [x for (m, a), d in L.items() if a == ano for x in d.values()]
    if not lst: print(ano, "sem locais"); continue
    n = len(lst); pc = lambda c: f"{100 * c / n:.1f}%"
    print(f"{ano}: {n:,} locais | {sum(x['s'] for x in lst):,} seções | {sum(x['el'] or 0 for x in lst):,} eleitores")
    print(f"      coordenada {pc(sum(1 for x in lst if x['la'] is not None and x['lo'] is not None))} | bairro {pc(sum(1 for x in lst if x['b']))}"
          f" | CEP {pc(sum(1 for x in lst if x['c']))} | perfil casado {pc(sum(1 for x in lst if 'pt' in x))}")
print(f"\nterritorio: {len(tam)} municípios, {sum(tam.values()) / 1e6:.1f} MB | micro: {len(tam_m)} municípios, {sum(tam_m.values()) / 1e6:.1f} MB")
print("maiores (micro):", [(n, round(s / 1e6, 1)) for n, s in sorted(tam_m.items(), key=lambda x: -x[1])[:3]])
for cod in ("3534401", "3505708"):
    f = MIC / f"{cod}.json"
    if f.exists():
        j = json.load(open(f, encoding="utf-8")); l24 = j["locais"].get("2024", [])
        print(f"{j['nome']} 2024: {len(l24)} locais | bairros {len({x.get('b') for x in l24 if x.get('b')})} | blocos de votos:",
              {a: list(b) for a, b in j["votos"].items()})
