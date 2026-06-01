import json
import time
from pathlib import Path

import pytest

from consulta_nfse_api.cliente import RateLimiter
from consulta_nfse_api.excecoes import ErroRateLimit


@pytest.fixture
def rate_limiter(tmp_path):
    arquivo = tmp_path / "rate_limit.json"
    return RateLimiter(arquivo)


def test_rate_limiter_sem_historico(rate_limiter):
    esperar = rate_limiter.verificar_intervalo("chave-teste")
    assert esperar is None


def test_rate_limiter_registrar_e_verificar(rate_limiter):
    rate_limiter.registrar_consulta("chave-teste")
    esperar = rate_limiter.verificar_intervalo("chave-teste", horas=0)
    assert esperar is not None
    assert esperar >= 0


def test_rate_limiter_bloqueia_intervalo(rate_limiter):
    rate_limiter.registrar_consulta("chave-bloqueio")
    with pytest.raises(ErroRateLimit):
        rate_limiter.aguardar_se_necessario("chave-bloqueio", horas=1)


def test_rate_limiter_force_ignora_bloqueio(rate_limiter):
    rate_limiter.registrar_consulta("chave-force")
    rate_limiter.aguardar_se_necessario("chave-force", horas=1, force=True)


def test_rate_limiter_chaves_diferentes(rate_limiter):
    rate_limiter.registrar_consulta("chave-a")
    esperar = rate_limiter.verificar_intervalo("chave-b", horas=0)
    assert esperar is None


def test_rate_limiter_persistencia(tmp_path):
    arquivo = tmp_path / "rate_limit.json"
    rl = RateLimiter(arquivo)
    rl.registrar_consulta("persistente")
    del rl

    rl2 = RateLimiter(arquivo)
    esperar = rl2.verificar_intervalo("persistente", horas=0)
    assert esperar is not None


def test_rate_limiter_arquivo_corrompido(tmp_path):
    arquivo = tmp_path / "rate_limit.json"
    arquivo.write_text("corrompido", encoding="utf-8")
    rl = RateLimiter(arquivo)
    esperar = rl.verificar_intervalo("qualquer")
    assert esperar is None
