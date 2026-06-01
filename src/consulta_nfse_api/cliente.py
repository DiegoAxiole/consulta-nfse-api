from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import httpx

from consulta_nfse_api.auth import CertificadoA1
from consulta_nfse_api.config import Settings
from consulta_nfse_api.excecoes import (
    ErroNaoEncontrado,
    ErroRateLimit,
    MENSAGENS_HTTP,
    levantar_por_status,
)
from consulta_nfse_api.modelos import Ambiente, Configuracao, normalizar_cnpj
from consulta_nfse_api.tracer import Tracer

RATE_LIMIT_FILE = Path.home() / ".consulta_nfse_api" / "rate_limit.json"
INTERVALO_DISTRIBUICAO_HORAS = 1
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0


class RateLimiter:
    """Controla o intervalo minimo entre consultas de distribuicao.

    A API ADN exige intervalo minimo de 1 hora entre consultas
    de distribuicao por NSU (regra 6.4 do manual).
    """

    def __init__(self, arquivo: Path = RATE_LIMIT_FILE):
        """Args:
            arquivo: Caminho do arquivo JSON para persistencia.
        """
        self._arquivo = arquivo
        self._dados: dict = self._carregar()

    def _carregar(self) -> dict:
        if self._arquivo.exists():
            try:
                return json.loads(self._arquivo.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _salvar(self):
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        self._arquivo.write_text(
            json.dumps(self._dados, indent=2), encoding="utf-8"
        )

    def registrar_consulta(self, chave: str):
        """Registra o timestamp da consulta para controle de intervalo.

        Args:
            chave: Identificador unico (ex: ``distribuicao:{CNPJ}``).
        """
        self._dados[chave] = time.time()
        self._salvar()

    def verificar_intervalo(
        self, chave: str, horas: float = INTERVALO_DISTRIBUICAO_HORAS
    ) -> Optional[float]:
        """Verifica quanto tempo falta para poder consultar novamente.

        Args:
            chave: Identificador unico.
            horas: Intervalo minimo em horas (padrao: 1).

        Returns:
            Segundos restantes ou None se ja pode consultar.
        """
        ts = self._dados.get(chave)
        if ts is None:
            return None
        decorrido = time.time() - ts
        if horas > 0:
            if decorrido < horas * 3600:
                return horas * 3600 - decorrido
            return None
        return decorrido

    def aguardar_se_necessario(
        self,
        chave: str,
        horas: float = INTERVALO_DISTRIBUICAO_HORAS,
        force: bool = False,
    ):
        """Levanta ErroRateLimit se o intervalo minimo nao foi respeitado.

        Args:
            chave: Identificador unico.
            horas: Intervalo minimo em horas.
            force: Se True, ignora o bloqueio.

        Raises:
            ErroRateLimit: Intervalo minimo nao respeitado e force=False.
        """
        esperar = self.verificar_intervalo(chave, horas)
        if esperar is not None and esperar > 0:
            if force:
                return
            raise ErroRateLimit(
                f"Aguardar {esperar / 60:.1f} min ate proxima consulta "
                f"(intervalo minimo de {horas}h, regra ADN 6.4)",
                aguardar_segundos=int(esperar),
            )


class NfseClient:
    """Cliente HTTP para a API ADN Nacional de distribuicao de NFSe.

    Gerencia autenticacao com certificado A1, sessao HTTP,
    rate limit e logging de trafego.

    Args:
        config: Objeto Configuracao com certificado e ambiente.
        settings: Objeto Settings do .env (alternativo a config).

    Example:
        >>> client = NfseClient()
        >>> dados = client.consultar_por_nsu(nsu=0)
        >>> print(dados.get("StatusProcessamento"))
    """

    def __init__(
        self,
        config: Optional[Configuracao] = None,
        settings: Optional[Settings] = None,
    ):
        if config:
            self._config = config
        elif settings:
            self._config = Configuracao(
                certificado_pfx=settings.certificado_pfx,
                senha_certificado=settings.senha_certificado,
                cnpj_prestador=settings.cnpj_prestador,
                ambiente=Ambiente(settings.ambiente),
            )
        else:
            settings = Settings()
            self._config = Configuracao(
                certificado_pfx=settings.certificado_pfx,
                senha_certificado=settings.senha_certificado,
                cnpj_prestador=settings.cnpj_prestador,
                ambiente=Ambiente(settings.ambiente),
            )

        self._cert = CertificadoA1(
            self._config.certificado_pfx, self._config.senha_certificado
        )
        self._client = self._criar_cliente()
        self._rate_limiter = RateLimiter()
        self._tracer: Optional[Tracer] = None

    def _criar_cliente(self) -> httpx.Client:
        """Cria o cliente HTTP com certificado mTLS.

        Returns:
            httpx.Client configurado com certificado A1.
        """
        cert_path, key_path = self._cert.exportar_pem()

        base = (
            "https://adn.producaorestrita.nfse.gov.br/contribuintes"
            if self._config.ambiente == Ambiente.HOMOLOGACAO
            else "https://adn.nfse.gov.br/contribuintes"
        )

        return httpx.Client(
            base_url=base,
            cert=(str(cert_path), str(key_path)),
            verify=True,
            timeout=60.0,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            event_hooks={
                "request": [self._trace_request],
                "response": [self._trace_response],
            },
        )

    @property
    def certificado(self) -> CertificadoA1:
        """Certificado digital A1 carregado."""
        return self._cert

    @property
    def config(self) -> Configuracao:
        """Configuracao atual do cliente."""
        return self._config

    @property
    def tipo_contribuinte(self) -> str:
        """Tipo do contribuinte: PF (CPF) ou PJ (CNPJ)."""
        return "PF" if len(self._doc_consulta) == 11 else "PJ"

    def start_trace(self, diretorio: str | Path = "debug"):
        """Ativa o logging de request/response em arquivos.

        Args:
            diretorio: Diretorio para salvar os logs (padrao: debug/).
        """
        self._tracer = Tracer(diretorio)

    def stop_trace(self):
        """Desativa o logging de trafego."""
        self._tracer = None

    def _trace_request(self, request: httpx.Request):
        if self._tracer:
            self._tracer.request(request)

    def _trace_response(self, response: httpx.Response):
        if self._tracer:
            self._tracer.response(response)

    def _validar_resposta(self, r: httpx.Response) -> dict:
        """Valida a resposta HTTP e retorna o JSON.

        Args:
            r: Resposta HTTP do httpx.

        Returns:
            Dict com o JSON da resposta.

        Raises:
            ErroRateLimit: Status 429.
            ErroNaoEncontrado: Status 404 com documento nao localizado.
            ErroAutenticacao, ErroServidor, etc: Conforme o status.
        """
        if r.status_code == 429:
            raise ErroRateLimit("Muitas requisicoes — aguarde e tente novamente")
        try:
            corpo = r.json()
        except Exception:
            corpo = {"mensagem": r.text}
        if r.status_code == 404:
            status = corpo.get("StatusProcessamento", "")
            if status == "NENHUM_DOCUMENTO_LOCALIZADO":
                return corpo
            raise ErroNaoEncontrado(
                corpo.get("Erros", [{}])[0].get("Descricao", "Recurso nao encontrado")
            )
        if r.is_error:
            levantar_por_status(r.status_code, r.text)
        return corpo

    def _enviar(self, method: str, path: str, **kwargs) -> dict:
        """Envia requisicao HTTP com retry em caso de timeout/erro 5xx.

        Args:
            method: Metodo HTTP (GET, POST).
            path: Caminho relativo a base_url.
            **kwargs: Argumentos adicionais do httpx.

        Returns:
            Dict com o JSON da resposta.

        Raises:
            ErroRateLimit: Nao faz retry para rate limit.
            httpx.TimeoutException: Apos MAX_RETRIES tentativas.
        """
        tentativa = 0
        while True:
            try:
                r = self._client.request(method, path, **kwargs)
                return self._validar_resposta(r)
            except httpx.TimeoutException:
                tentativa += 1
                if tentativa >= MAX_RETRIES:
                    raise
                time.sleep(RETRY_BACKOFF**tentativa)
            except ErroRateLimit:
                raise
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (500, 502, 503) and tentativa < MAX_RETRIES:
                    tentativa += 1
                    time.sleep(RETRY_BACKOFF**tentativa)
                    continue
                levantar_por_status(e.response.status_code, e.response.text)
                raise
            except httpx.HTTPError:
                tentativa += 1
                if tentativa >= MAX_RETRIES:
                    raise
                time.sleep(RETRY_BACKOFF**tentativa)

    @staticmethod
    def _param_consulta(doc: str) -> tuple[str, str]:
        """Define o parametro de consulta conforme PF ou PJ.

        Args:
            doc: CNPJ (14 digitos) ou CPF (11 digitos).

        Returns:
            Tupla (nome_parametro, valor).
        """
        num = normalizar_cnpj(doc)
        if len(num) == 11:
            return "cpfConsulta", num
        return "cnpjConsulta", num

    @property
    def _doc_consulta(self) -> str:
        """CNPJ/CPF extraido do certificado."""
        raw = self._cert.cnpj or ""
        doc = raw.split(":")[-1] if ":" in raw else raw
        return normalizar_cnpj(doc)

    def consultar_por_nsu(
        self, nsu: int, doc_consulta: Optional[str] = None, force: bool = False
    ) -> dict:
        """Consulta a API de distribuicao por NSU.

        Args:
            nsu: NSU inicial para consulta.
            doc_consulta: CNPJ/CPF (opcional, extraido do certificado).
            force: Ignora o rate limit de 1h.

        Returns:
            Dict JSON com a resposta da API.

        Raises:
            ErroRateLimit: Intervalo minimo nao respeitado (use force=True).
        """
        doc = doc_consulta or self._doc_consulta
        param_name, param_value = self._param_consulta(doc)
        chave_rate = f"distribuicao:{param_value}"
        self._rate_limiter.aguardar_se_necessario(chave_rate, force=force)
        self._rate_limiter.registrar_consulta(chave_rate)
        params = {param_name: param_value, "lote": "true"}
        return self._enviar("GET", f"/dfe/{nsu}", params=params)

    def fechar(self):
        """Fecha a sessao HTTP e limpa arquivos temporarios do certificado."""
        self._client.close()
        self._cert.limpar()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.fechar()
