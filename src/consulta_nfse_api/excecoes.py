from __future__ import annotations


class NfseError(Exception):
    """Erro base do pacote consulta-nfse-api."""


class ErroAutenticacao(NfseError):
    """Erro de autenticacao (401, 403, 496)."""


class ErroCertificado(NfseError):
    """Erro relacionado ao certificado digital A1."""


class ErroRateLimit(NfseError):
    """Rate limit atingido (429) ou intervalo minimo nao respeitado.

    Args:
        mensagem: Descricao do erro.
        aguardar_segundos: Tempo recomendado de espera (0 se desconhecido).
    """

    def __init__(self, mensagem: str, aguardar_segundos: int = 0):
        self.aguardar_segundos = aguardar_segundos
        super().__init__(mensagem)


class ErroServidor(NfseError):
    """Erro no servidor ADN (500, 502, 503)."""


class ErroValidacao(NfseError):
    """Erro de validacao de dados de entrada ou schema XML."""


class ErroApi(NfseError):
    """Erro retornado pela API ADN com codigo de negocio.

    Args:
        mensagem: Descricao do erro.
        codigo: Codigo de erro retornado pela API.
        detalhes: Detalhes adicionais do erro.
    """

    def __init__(self, mensagem: str, codigo: str = "", detalhes: str = ""):
        self.codigo = codigo
        self.detalhes = detalhes
        super().__init__(mensagem)


class ErroNaoEncontrado(NfseError):
    """Recurso nao encontrado (404)."""


MENSAGENS_HTTP: dict[int, str] = {
    400: "Requisicao invalida — verifique os parametros enviados",
    401: "Nao autorizado — certifique-se de que o certificado e valido",
    403: "Acesso negado — o certificado nao tem permissao para este recurso",
    404: "Recurso nao encontrado — verifique o identificador informado",
    429: "Muitas requisicoes — aguarde antes de novas consultas",
    496: "Certificado necessario — a API exige certificado digital A1",
    500: "Erro interno do servidor ADN",
    502: "Servidor ADN temporariamente indisponivel",
    503: "Servico ADN em manutencao",
}


def levantar_por_status(status_code: int, corpo: str = "") -> None:
    """Levanta a excecao adequada conforme o codigo HTTP.

    Args:
        status_code: Codigo HTTP de resposta.
        corpo: Corpo da resposta (opcional, para diagnostico).

    Raises:
        ErroAutenticacao: Para 401, 403, 496.
        ErroNaoEncontrado: Para 404.
        ErroRateLimit: Para 429.
        ErroServidor: Para 500, 502, 503.
        ErroValidacao: Para 400.
        NfseError: Para demais codigos.
    """
    msg = MENSAGENS_HTTP.get(status_code, f"Erro HTTP {status_code}")

    if status_code in (401, 496):
        raise ErroAutenticacao(msg)
    if status_code == 403:
        raise ErroAutenticacao(msg)
    if status_code == 404:
        raise ErroNaoEncontrado(msg)
    if status_code == 429:
        raise ErroRateLimit(msg)
    if status_code in (500, 502, 503):
        raise ErroServidor(msg)
    if status_code == 400:
        raise ErroValidacao(msg)

    raise NfseError(msg)
