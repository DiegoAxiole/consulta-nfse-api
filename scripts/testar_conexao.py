from __future__ import annotations

import sys
from pathlib import Path

try:
    from consulta_nfse_api.cliente import NfseClient
    from consulta_nfse_api.config import Settings
    from consulta_nfse_api.download import _descompactar_xml
    from consulta_nfse_api.excecoes import NfseError
    from consulta_nfse_api.modelos import (
        DFeLoteResponse,
        DownloadResult,
        SincronizarResult,
        normalizar_cnpj,
    )
except ImportError as e:
    print(f"Erro: pacote consulta-nfse-api nao encontrado ({e})")
    print("Execute o script da raiz do projeto com: uv run python scripts/testar_conexao.py")
    sys.exit(1)

VERDE = "\033[92m"
VERMELHO = "\033[91m"
AMARELO = "\033[93m"
AZUL = "\033[94m"
NEGRITO = "\033[1m"
RESET = "\033[0m"
PASS = f"{VERDE}[OK]{RESET}"
FAIL = f"{VERMELHO}[FALHOU]{RESET}"
SKIP = f"{AMARELO}[PULOU]{RESET}"

TOTAL_TESTES = 5
passou = 0
falhou = 0
pulou = 0


def titulo(n: int, msg: str):
    print(f"\n{AZUL}[{n}/{TOTAL_TESTES}]{RESET} {msg}...")


def ok(msg: str):
    global passou
    passou += 1
    print(f"  {PASS} {msg}")


def fail(msg: str):
    global falhou
    falhou += 1
    print(f"  {FAIL} {msg}")


def skip(msg: str):
    global pulou
    pulou += 1
    print(f"  {SKIP} {msg}")


def cabecalho():
    settings = Settings()
    print(f"{NEGRITO}{'=' * 55}{RESET}")
    print(f"{NEGRITO}  Teste de Conexao ADN{' ' * 22}{RESET}")
    print(f"{NEGRITO}{'=' * 55}{RESET}")
    print(f"  Ambiente : {AZUL}{settings.ambiente}{RESET}")
    print(f"  URL      : {settings.base_url}")
    print(f"  Cert.    : {settings.certificado_pfx or AMARELO + '(nao configurado)' + RESET}")
    print(f"  CNPJ     : {settings.cnpj_prestador or AMARELO + '(nao configurado)' + RESET}")
    print(f"{'=' * 55}\n")


def validar_configuracao() -> bool:
    titulo(1, "Validando configuracao")
    settings = Settings()
    erros = []
    if not settings.certificado_pfx:
        erros.append("NFSE_CERTIFICADO_PFX nao configurado")
    elif not Path(settings.certificado_pfx).exists():
        erros.append(f"Arquivo de certificado nao encontrado: {settings.certificado_pfx}")
    if not settings.senha_certificado:
        erros.append("NFSE_SENHA_CERTIFICADO nao configurada")
    if not settings.cnpj_prestador:
        print("  [dim]  NFSE_CNPJ_PRESTADOR: nao configurado (sera extraido do certificado)[/dim]")
    if settings.ambiente not in ("homologacao", "producao"):
        erros.append(f"Ambiente invalido: {settings.ambiente}")
    if erros:
        for e in erros:
            fail(e)
        return False
    ok(f".env valido — ambiente={settings.ambiente}, CNPJ={settings.cnpj_prestador}")
    return True


def testar_certificado() -> bool:
    titulo(2, "Testando certificado A1")
    try:
        settings = Settings()
        client = NfseClient(settings=settings)
        resumo = client.certificado.resumo()
        client.fechar()
        vencimento = resumo.get("valido_ate", "desconhecido")
        emissor = resumo.get("emissor", "desconhecido")
        cnpj = resumo.get("cnpj", "")
        tipo = "PF" if len(normalizar_cnpj(cnpj.split(":")[-1] if ":" in cnpj else cnpj)) == 11 else "PJ"
        ok(f"Certificado carregado — emissor={emissor}, valido ate {vencimento}, tipo={tipo}")
        return True
    except Exception as e:
        fail(f"Falha ao carregar certificado: {e}")
        return False


def testar_consulta_nsu(client: NfseClient) -> DFeLoteResponse | None:
    titulo(3, "Conectando a API ADN (NSU=0)")
    try:
        doc = client._doc_consulta
        param_name, _ = NfseClient._param_consulta(doc)
        dados = client.consultar_por_nsu(0, doc, force=True)
        resposta = DFeLoteResponse.model_validate(dados)
        status = resposta.status_processamento
        total = len(resposta.lote_dfe)
        ok(f"Conectado — status={status}, documentos no lote={total}, usando {param_name}")
        if resposta.ultimo_nsu:
            print(f"  [dim]  ultNSU={resposta.ultimo_nsu}, maxNSU={resposta.max_nsu or 'N/A'}[/dim]")
        return resposta
    except NfseError as e:
        fail(f"Erro ADN: {e}")
        return None
    except Exception as e:
        fail(f"Falha na conexao: {e}")
        return None


def testar_sincronizar(dfe: DFeLoteResponse) -> bool:
    titulo(4, "Criando SincronizarResult a partir dos dados ja baixados")
    try:
        if not dfe.tem_documentos:
            skip("Nenhum documento no lote")
            return True
        documentos = []
        for doc in dfe.lote_dfe:
            xml = _descompactar_xml(doc.arquivo_xml)
            pasta = doc.data_hora_geracao.strftime("%Y.%m")
            dir_path = Path("xmls_teste") / pasta
            dir_path.mkdir(parents=True, exist_ok=True)
            arquivo = dir_path / f"{doc.chave_acesso}.xml"
            arquivo.write_text(xml, encoding="utf-8")
            documentos.append(
                DownloadResult(
                    nsu=doc.nsu,
                    chave_acesso=doc.chave_acesso,
                    tipo=doc.tipo_documento or "NFSE",
                    tipo_evento=doc.tipo_evento,
                    data_hora_geracao=doc.data_hora_geracao,
                    arquivo_xml=arquivo.resolve(),
                )
            )
        resultado = SincronizarResult(
            status=dfe.status_processamento,
            documentos=documentos,
            ultimo_nsu=dfe.ultimo_nsu,
        )
        ok(f"SincronizarResult criado — {len(resultado.documentos)} documento(s), "
           f"status={resultado.status}")
        if documentos:
            amostra = documentos[0]
            print(f"  [dim]  Amostra: NSU={amostra.nsu}, chave={amostra.chave_acesso}, "
                  f"arquivo={amostra.arquivo_xml.name}[/dim]")
        if resultado.ultimo_nsu:
            print(f"  [dim]  ultNSU={resultado.ultimo_nsu}[/dim]")
        return True
    except NfseError as e:
        fail(f"Erro ADN: {e}")
        return False
    except Exception as e:
        fail(f"Falha: {e}")
        return False


def testar_importacao_direta() -> bool:
    titulo(5, "Importacao direta do pacote")
    try:
        from consulta_nfse_api import (
            NfseClient,
            Ambiente,
            DownloadResult,
            SincronizarResult,
            normalizar_cnpj,
        )
        ok(f"Pacote importado — DownloadResult, SincronizarResult, Ambiente disponiveis")
        return True
    except ImportError as e:
        fail(f"Falha na importacao: {e}")
        return False


def rodape():
    print(f"\n{NEGRITO}{'=' * 55}{RESET}")
    total = passou + falhou + pulou
    if falhou == 0:
        print(f"  Resumo: {VERDE}{passou}/{total} testes OK{' ' * 35}{RESET}")
    else:
        print(f"  Resumo: {VERDE}{passou} passaram "
              f"{RESET}| {VERMELHO}{falhou} falharam{RESET}"
              f" | {AMARELO}{pulou} pulados{RESET}")
    print(f"{NEGRITO}{'=' * 55}{RESET}")
    return falhou == 0


def main():
    cabecalho()

    if not validar_configuracao():
        rodape()
        sys.exit(1)

    settings = Settings()
    client = NfseClient(settings=settings)
    client.start_trace()

    testar_certificado()

    doc = client._doc_consulta
    param_name, _ = NfseClient._param_consulta(doc)
    print(f"\n  Documento consulta: {doc} ({client.tipo_contribuinte})")
    print(f"  Parametro API: {param_name}")

    dfe = testar_consulta_nsu(client)
    if dfe:
        testar_sincronizar(dfe)
    else:
        skip("Pulado (consulta NSU falhou)")

    client.fechar()

    testar_importacao_direta()

    sucesso = rodape()
    sys.exit(0 if sucesso else 1)


if __name__ == "__main__":
    main()
