from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


class CertificadoA1:
    """Gerencia certificado digital A1 no formato PFX/P12.

    Extrai certificado e chave privada, exporta para PEM
    temporario (necessario para mTLS com httpx) e limpa
    arquivos ao final.

    Args:
        arquivo_pfx: Caminho do arquivo .pfx ou .p12.
        senha: Senha para descriptografar o arquivo.

    Raises:
        FileNotFoundError: Arquivo nao encontrado.
        ValueError: PFX sem certificado valido.
    """

    def __init__(self, arquivo_pfx: str | Path, senha: str):
        self.arquivo = Path(arquivo_pfx)
        if not self.arquivo.exists():
            raise FileNotFoundError(f"Certificado nao encontrado: {self.arquivo}")
        self.senha = senha
        self._certificado: Optional[x509.Certificate] = None
        self._chave: Optional[rsa.RSAPrivateKey] = None
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None
        self._cert_pem_path: Optional[Path] = None
        self._key_pem_path: Optional[Path] = None
        self._carregar()

    def _carregar(self):
        dados = self.arquivo.read_bytes()
        self._chave, self._certificado, _ = (
            pkcs12.load_key_and_certificates(dados, self.senha.encode())
        )
        if self._certificado is None:
            raise ValueError("Nenhum certificado encontrado no arquivo PFX")

    @property
    def certificado(self) -> x509.Certificate:
        """Certificado X.509 carregado do PFX."""
        assert self._certificado is not None
        return self._certificado

    @property
    def chave(self) -> rsa.RSAPrivateKey:
        """Chave privada RSA extraida do PFX."""
        assert self._chave is not None
        return self._chave

    @property
    def cnpj(self) -> Optional[str]:
        """CNPJ ou CPF extraido do campo CN do certificado."""
        try:
            for attr in self.certificado.subject:
                if attr.oid == NameOID.COMMON_NAME:
                    return attr.value
        except Exception:
            return None

    @property
    def nome_emissor(self) -> str:
        """Nome do emissor do certificado no formato RFC 4514."""
        return self.certificado.issuer.rfc4514_string()

    @property
    def valido_ate(self):
        """Data/hora de expiracao do certificado."""
        return self.certificado.not_valid_after_utc

    @property
    def valido(self) -> bool:
        """True se o certificado esta dentro do periodo de validade."""
        from datetime import datetime, timezone

        agora = datetime.now(timezone.utc)
        return (
            self.certificado.not_valid_after_utc >= agora
            and self.certificado.not_valid_before_utc <= agora
        )

    def exportar_pem(self) -> tuple[Path, Path]:
        """Exporta certificado e chave para arquivos PEM temporarios.

        Os arquivos sao criados em um diretorio temporario e
        podem ser usados como ``cert`` e ``key`` pelo httpx.

        Returns:
            Tupla (caminho_cert_pem, caminho_key_pem).
        """
        if self._cert_pem_path is not None and self._key_pem_path is not None:
            return self._cert_pem_path, self._key_pem_path

        self._temp_dir = tempfile.TemporaryDirectory()
        base = Path(self._temp_dir.name)

        cert_pem = self.certificado.public_bytes(serialization.Encoding.PEM)
        key_pem = self.chave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

        cert_path = base / "cert.pem"
        key_path = base / "key.pem"
        cert_path.write_bytes(cert_pem)
        key_path.write_bytes(key_pem)

        self._cert_pem_path = cert_path
        self._key_pem_path = key_path
        return cert_path, key_path

    def limpar(self):
        """Remove os arquivos PEM temporarios."""
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None
            self._cert_pem_path = None
            self._key_pem_path = None

    def resumo(self) -> dict:
        """Resumo das informacoes do certificado para exibicao.

        Returns:
            Dict com CNPJ, validade, emissor e arquivo.
        """
        return {
            "cnpj": self.cnpj,
            "valido": self.valido,
            "valido_ate": self.valido_ate.isoformat(),
            "emissor": self.nome_emissor,
            "arquivo": str(self.arquivo),
        }
