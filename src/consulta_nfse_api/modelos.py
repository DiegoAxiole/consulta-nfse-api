from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Ambiente(str, Enum):
    """Ambiente da API ADN Nacional."""
    PRODUCAO = "producao"
    HOMOLOGACAO = "homologacao"


class Configuracao(BaseModel):
    """Configuracao para conexao com a API ADN.

    Args:
        certificado_pfx: Caminho absoluto para o arquivo .pfx do certificado A1.
        senha_certificado: Senha do arquivo .pfx.
        cnpj_prestador: CNPJ do prestador (opcional, extraido do certificado).
        ambiente: Ambiente da API (producao ou homologacao).
    """
    certificado_pfx: str
    senha_certificado: str
    cnpj_prestador: str = ""
    ambiente: Ambiente = Ambiente.PRODUCAO

    @field_validator("cnpj_prestador")
    @classmethod
    def validar_cnpj(cls, v: str) -> str:
        if v:
            return _validar_cnpj(v)
        return v


def _limpar_cnpj(v: str) -> str:
    return v.replace(".", "").replace("-", "").replace("/", "")


def _validar_cnpj(v: str) -> str:
    v = _limpar_cnpj(v)
    if len(v) not in (11, 14) or not v.isdigit():
        raise ValueError(f"CNPJ/CPF deve ter 11 ou 14 digitos, got '{v}'")
    return v


def normalizar_cnpj(cnpj: str) -> str:
    """Remove mascara de formatacao de CNPJ/CPF.

    Args:
        cnpj: CNPJ ou CPF com ou sem mascara.

    Returns:
        Apenas digitos numericos.
    """
    return _limpar_cnpj(cnpj)


class DFeDocumento(BaseModel):
    """Documento do lote DFe retornado pela API de distribuicao.

    Args:
        nsu: Numero sequencial unico do documento.
        chave_acesso: Chave de acesso de 44 digitos.
        tipo_documento: Tipo do documento (NFSE, EVENTO).
        tipo_evento: Subtipo quando tipo_documento for EVENTO (ex: CANCELAMENTO).
        data_hora_geracao: Data/hora de geracao do documento.
        arquivo_xml: Conteudo XML comprimido (base64 + gzip).
        cnpj_emitente: CNPJ do emitente (opcional).
        cnpj_destinatario: CNPJ do destinatario (opcional).
        valor_servicos: Valor dos servicos (opcional).
    """
    nsu: int = Field(alias="NSU")
    chave_acesso: str = Field(alias="ChaveAcesso")
    tipo_documento: Optional[str] = Field(default=None, alias="TipoDocumento")
    tipo_evento: Optional[str] = Field(default=None, alias="TipoEvento")
    data_hora_geracao: datetime = Field(alias="DataHoraGeracao")
    arquivo_xml: str = Field(alias="ArquivoXml")
    cnpj_emitente: Optional[str] = Field(default=None, alias="CnpjEmitente")
    cnpj_destinatario: Optional[str] = Field(default=None, alias="CnpjDestinatario")
    valor_servicos: Optional[str] = Field(default=None, alias="ValorServicos")


class DFeLoteResponse(BaseModel):
    """Resposta completa da API de distribuicao por NSU.

    Args:
        status_processamento: Status retornado pela API.
        lote_dfe: Lista de documentos do lote.
        ultimo_nsu: Ultimo NSU processado neste lote.
        max_nsu: Maximo NSU disponivel na base.
        erros: Erros de negocio retornados pela API.
    """
    status_processamento: str = Field(default="", alias="StatusProcessamento")
    lote_dfe: list[DFeDocumento] = Field(default_factory=list, alias="LoteDFe")
    ultimo_nsu: Optional[str] = Field(default=None, alias="UltimoNSU")
    max_nsu: Optional[str] = Field(default=None, alias="MaxNSU")
    erros: list[dict] = Field(default_factory=list, alias="Erros")

    @property
    def tem_documentos(self) -> bool:
        """True se o lote contem documentos."""
        return len(self.lote_dfe) > 0


class DownloadResult(BaseModel):
    """Resultado do download de um unico documento.

    Este modelo contem os metadados do documento baixado.
    O consumidor pode usar estes dados para registrar no seu
    banco de dados (ex: SQLite) e controlar o progresso da
    sincronizacao.

    Args:
        nsu: NSU do documento.
        chave_acesso: Chave de acesso de 44 digitos.
        tipo: Tipo do documento (NFSE, EVENTO).
        tipo_evento: Subtipo quando for evento (ex: CANCELAMENTO).
        data_hora_geracao: Data/hora de geracao.
        arquivo_xml: Caminho absoluto do arquivo XML salvo em disco.
    """
    nsu: int
    chave_acesso: str
    tipo: str
    tipo_evento: Optional[str] = None
    data_hora_geracao: datetime
    arquivo_xml: Path


class SincronizarResult(BaseModel):
    """Resultado completo de uma sincronizacao via NSU.

    Args:
        status: Status retornado pela API de distribuicao.
        documentos: Lista de documentos baixados com metadados.
        ultimo_nsu: Ultimo NSU processado (usar na proxima chamada).
    """
    status: str
    documentos: list[DownloadResult]
    ultimo_nsu: Optional[str] = None
