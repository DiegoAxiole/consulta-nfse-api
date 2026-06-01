from pathlib import Path

import pytest


@pytest.fixture
def cnpj_valido():
    return "12345678000199"


@pytest.fixture
def id_nfse_valido():
    return "NFSE-2025-00000001"
