from __future__ import annotations

import getpass
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from consulta_nfse_api.cliente import NfseClient
from consulta_nfse_api.config import Settings
from consulta_nfse_api.download import sincronizar as baixar_lote
from consulta_nfse_api.excecoes import (
    ErroAutenticacao,
    ErroCertificado,
    ErroNaoEncontrado,
    ErroRateLimit,
    ErroServidor,
    NfseError,
)
from consulta_nfse_api.modelos import normalizar_cnpj

app = typer.Typer(
    name="consulta-nfse-api",
    help="Cliente para download de XMLs da NFSe via API ADN Nacional",
)
console = Console()


def _com_trace(client: NfseClient, debug: bool):
    if debug:
        client.start_trace()
        console.print("[dim]Trace ativo — dados salvos em debug/[/dim]")


def _exibir_erro(e: NfseError):
    if isinstance(e, ErroRateLimit):
        console.print(f"[yellow]Rate limit: {e}[/yellow]")
    elif isinstance(e, ErroAutenticacao):
        console.print(f"[red]Erro de autenticacao: {e}[/red]")
        console.print("[dim]Verifique o certificado A1 e a senha[/dim]")
    elif isinstance(e, ErroCertificado):
        console.print(f"[red]Erro no certificado: {e}[/red]")
    elif isinstance(e, ErroNaoEncontrado):
        console.print(f"[yellow]Nao encontrado: {e}[/yellow]")
    elif isinstance(e, ErroServidor):
        console.print(f"[red]Erro no servidor ADN: {e}[/red]")
        console.print("[dim]Tente novamente mais tarde[/dim]")
    else:
        console.print(f"[red]Erro: {e}[/red]")


def _criar_client(
    cert: Optional[str],
    senha: Optional[str],
    ambiente: Optional[str],
) -> NfseClient:
    """Cria NfseClient a partir de CLI flags ou .env.

    Args:
        cert: Caminho do .pfx (opcional, fallback pro .env).
        senha: Senha do .pfx (opcional, prompt se --cert sem --senha).
        ambiente: Ambiente (opcional, fallback pro .env).

    Returns:
        NfseClient configurado.
    """
    if cert:
        pfx = Path(cert)
        if not pfx.exists():
            console.print(f"[red]Certificado nao encontrado:[/red] {pfx}")
            raise typer.Exit(code=1)
        pwd = senha
        if pwd is None:
            pwd = getpass.getpass("Senha do certificado: ")
        settings = Settings()
        return NfseClient(
            config=type(
                "Config",
                (),
                {
                    "certificado_pfx": str(pfx.resolve()),
                    "senha_certificado": pwd,
                    "cnpj_prestador": settings.cnpj_prestador,
                    "ambiente": (
                        __import__(
                            "consulta_nfse_api.modelos", fromlist=["Ambiente"]
                        ).Ambiente(ambiente or settings.ambiente)
                    ),
                },
            )()
        )
    return NfseClient()


@app.command()
def info(
    cert: Optional[str] = typer.Option(None, "--cert", help="Caminho do .pfx (opcional)"),
    senha: Optional[str] = typer.Option(None, "--senha", help="Senha do .pfx"),
    ambiente: Optional[str] = typer.Option(None, "--ambiente", help="producao ou homologacao"),
    debug: bool = typer.Option(False, "--debug", help="Salva request/response em debug/"),
):
    """Exibe informacoes do certificado digital e configuracao."""
    try:
        client = _criar_client(cert, senha, ambiente)
        _com_trace(client, debug)
        cert_info = client.certificado.resumo()

        table = Table(title="Certificado A1")
        table.add_column("Campo", style="cyan")
        table.add_column("Valor")
        for k, v in cert_info.items():
            table.add_row(k, str(v))

        console.print(table)
        console.print(f"\nAmbiente: {client.config.ambiente.value}")
        console.print(f"Tipo: {client.tipo_contribuinte}")
        console.print(f"Base URL: {client._client.base_url}")
    except NfseError as e:
        _exibir_erro(e)
        raise typer.Exit(code=1)
    finally:
        client.fechar()


@app.command()
def sincronizar(
    nsu: int = typer.Option(0, "--nsu", help="NSU inicial (0 para inicio)"),
    destino: str = typer.Option("xmls", "--destino", "-d", help="Diretorio para salvar os XMLs"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Ignorar rate limit de 1h"
    ),
    cert: Optional[str] = typer.Option(
        None, "--cert", help="Caminho do .pfx (opcional, fallback pro .env)"
    ),
    senha: Optional[str] = typer.Option(
        None, "--senha", help="Senha do .pfx (prompt se omitida com --cert)"
    ),
    ambiente: Optional[str] = typer.Option(
        None, "--ambiente", help="producao ou homologacao"
    ),
    debug: bool = typer.Option(False, "--debug", help="Salva request/response em debug/"),
):
    """Baixa XMLs das NFSe via API de distribuicao por NSU.

    Os XMLs sao salvos em ``{destino}/YYYY.MM/{chave_acesso}.xml``.
    O ultimo NSU processado e exibido ao final para uso na
    proxima sincronizacao.
    """
    try:
        client = _criar_client(cert, senha, ambiente)
        _com_trace(client, debug)
        doc = client._doc_consulta
        param_name, _ = NfseClient._param_consulta(doc)

        with console.status(
            f"Sincronizando a partir do NSU {nsu} ({client.tipo_contribuinte}, "
            f"{param_name})..."
        ):
            resultado = baixar_lote(client, nsu, destino, force=force)

        if not resultado.documentos:
            console.print("[yellow]Nenhum documento encontrado.[/yellow]")
            raise typer.Exit()

        table = Table(
            title=f"Documentos baixados: {len(resultado.documentos)}"
        )
        table.add_column("NSU", style="cyan")
        table.add_column("Chave de Acesso")
        table.add_column("Tipo")
        table.add_column("Arquivo")

        for doc in resultado.documentos:
            table.add_row(
                str(doc.nsu),
                doc.chave_acesso,
                doc.tipo_evento or doc.tipo,
                str(doc.arquivo_xml.name),
            )

        console.print(table)
        if resultado.ultimo_nsu:
            console.print(
                f"\n[green]Ultimo NSU processado:[/green] "
                f"{resultado.ultimo_nsu}"
            )
            console.print(
                "[dim]Use --nsu {0} na proxima sincronizacao[/dim]".format(
                    resultado.ultimo_nsu
                )
            )
    except NfseError as e:
        _exibir_erro(e)
        raise typer.Exit(code=1)
    finally:
        client.fechar()


if __name__ == "__main__":
    app()
