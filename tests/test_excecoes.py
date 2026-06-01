import pytest

from consulta_nfse_api.excecoes import (
    ErroApi,
    ErroAutenticacao,
    ErroCertificado,
    ErroNaoEncontrado,
    ErroRateLimit,
    ErroServidor,
    ErroValidacao,
    MENSAGENS_HTTP,
    NfseError,
    levantar_por_status,
)


def test_erro_base():
    e = NfseError("erro genérico")
    assert str(e) == "erro genérico"


def test_erro_autenticacao():
    with pytest.raises(ErroAutenticacao):
        levantar_por_status(401)


def test_erro_autenticacao_496():
    with pytest.raises(ErroAutenticacao):
        levantar_por_status(496)


def test_erro_nao_encontrado():
    with pytest.raises(ErroNaoEncontrado):
        levantar_por_status(404)


def test_erro_rate_limit():
    with pytest.raises(ErroRateLimit):
        levantar_por_status(429)


def test_erro_servidor_500():
    with pytest.raises(ErroServidor):
        levantar_por_status(500)


def test_erro_servidor_503():
    with pytest.raises(ErroServidor):
        levantar_por_status(503)


def test_erro_validacao():
    with pytest.raises(ErroValidacao):
        levantar_por_status(400)


def test_rate_limit_com_segundos():
    e = ErroRateLimit("muitas requisições", aguardar_segundos=3600)
    assert e.aguardar_segundos == 3600
    assert "muitas" in str(e)


def test_erro_api():
    e = ErroApi("erro de negócio", codigo="ERR-001", detalhes="detalhes")
    assert e.codigo == "ERR-001"
    assert e.detalhes == "detalhes"


def test_erro_certificado():
    e = ErroCertificado("certificado inválido")
    assert "certificado" in str(e)


def test_http_desconhecido():
    with pytest.raises(NfseError):
        levantar_por_status(418)
