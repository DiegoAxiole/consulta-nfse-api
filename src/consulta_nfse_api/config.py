from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracoes carregadas do arquivo .env.

    Variaveis de ambiente com prefixo ``NFSE_`` sao mapeadas
    automaticamente (ex: ``NFSE_CERTIFICADO_PFX``).

    Args:
        certificado_pfx: Caminho do arquivo .pfx.
        senha_certificado: Senha do certificado.
        ambiente: ``producao`` ou ``homologacao``.
        cnpj_prestador: CNPJ do prestador (opcional, extraido do cert).
    """

    model_config = SettingsConfigDict(
        env_prefix="NFSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    certificado_pfx: str = ""
    senha_certificado: str = ""
    ambiente: str = "producao"
    cnpj_prestador: str = ""

    @property
    def base_url(self) -> str:
        """URL base da API ADN conforme o ambiente."""
        if self.ambiente == "homologacao":
            return "https://adn.producaorestrita.nfse.gov.br/contribuintes"
        return "https://adn.nfse.gov.br/contribuintes"

    @property
    def cnc_url(self) -> str:
        """URL do CNC (Cadastro Nacional de Contribuintes) conforme ambiente."""
        if self.ambiente == "homologacao":
            return "https://adn.producaorestrita.nfse.gov.br/cnc/consulta"
        return "https://adn.nfse.gov.br/cnc/consulta"
