from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import httpx

DEBUG_DIR = Path("debug")


class Tracer:
    """Registra requisicoes e respostas HTTP em arquivos para depuracao.

    Cada request/response e salvo em um par de arquivos
    ``{timestamp}_{seq}_request.txt`` e ``{timestamp}_{seq}_response.txt``
    no diretorio configurado.

    Args:
        diretorio: Diretorio para salvar os logs (padrao: ``debug/``).
    """

    def __init__(self, diretorio: str | Path = "debug"):
        self._dir = Path(diretorio)
        self._sessao: Optional[str] = None
        self._contador = 0

    def _iniciar_sessao(self):
        if self._sessao is None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            self._sessao = ts
            self._dir.mkdir(parents=True, exist_ok=True)

    def _proximo_id(self) -> str:
        self._iniciar_sessao()
        self._contador += 1
        seq = f"{self._contador:03d}"
        return f"{self._sessao}_{seq}"

    def _salvar(self, nome: str, conteudo: str):
        caminho = self._dir / nome
        caminho.write_text(conteudo, encoding="utf-8")

    def _format_headers(self, headers: httpx.Headers) -> str:
        return "\n".join(f"{k}: {v}" for k, v in headers.items())

    def request(self, request: httpx.Request):
        """Registra uma requisicao HTTP em arquivo.

        Args:
            request: Objeto de requisicao do httpx.
        """
        req_id = self._proximo_id()
        url = str(request.url)
        metodo = request.method

        cabecalhos = self._format_headers(request.headers)
        corpo = ""
        if request.content:
            try:
                corpo = request.content.decode("utf-8")
            except UnicodeDecodeError:
                corpo = f"[binario {len(request.content)} bytes]"

        blocos = [
            f"=== REQUEST #{self._contador} ===",
            f"{metodo} {url}",
            "",
            "--- Headers ---",
            cabecalhos,
        ]
        if corpo:
            blocos.extend(["", "--- Body ---", corpo])
        blocos.append("")

        self._salvar(f"{req_id}_request.txt", "\n".join(blocos))

    def response(self, response: httpx.Response):
        """Registra uma resposta HTTP em arquivo.

        Args:
            response: Objeto de resposta do httpx.
        """
        if self._contador == 0:
            return
        response.read()
        req_id = f"{self._sessao}_{self._contador:03d}"

        cabecalhos = self._format_headers(response.headers)
        corpo = ""
        ctype = response.headers.get("content-type", "")
        if "json" in ctype:
            try:
                corpo = json.dumps(response.json(), indent=2, ensure_ascii=False)
            except Exception:
                corpo = response.text
        elif "xml" in ctype or "text" in ctype:
            corpo = response.text
        else:
            corpo = f"[{len(response.content)} bytes, {ctype}]"

        blocos = [
            f"=== RESPONSE #{self._contador} ===",
            f"{response.status_code} {response.reason_phrase}",
            "",
            "--- Headers ---",
            cabecalhos,
        ]
        if corpo:
            blocos.extend(["", "--- Body ---", corpo])
        blocos.append("")

        self._salvar(f"{req_id}_response.txt", "\n".join(blocos))

    def limpar(self):
        """Remove todos os arquivos de log do diretorio."""
        if self._dir.exists():
            import shutil

            shutil.rmtree(self._dir)
        self._sessao = None
        self._contador = 0
