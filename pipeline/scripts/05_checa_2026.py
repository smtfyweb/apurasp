import requests
B = "https://cdn.tse.jus.br/estatistica/sead"
for u in [f"{B}/odsele/votacao_candidato_munzona/votacao_candidato_munzona_2026.zip",
          f"{B}/odsele/votacao_partido_munzona/votacao_partido_munzona_2026.zip",
          f"{B}/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2026.zip",
          f"{B}/odsele/votacao_secao/votacao_secao_2026_SP.zip",
          f"{B}/eleicoes/eleicoes2026/buweb/bweb_1t_SP_051020261403.zip"]:
    try:
        h = requests.head(u, allow_redirects=True, timeout=30)
        print(h.status_code, f"{int(h.headers.get('Content-Length', 0))/1e6:8.0f} MB", u.split("/")[-1])
    except Exception as e:
        print("ERRO", u.split("/")[-1], e)
