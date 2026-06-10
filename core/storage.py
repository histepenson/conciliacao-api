"""
Cliente de storage S3-compatible (Railway Bucket Storage).

Substitui o armazenamento em disco local (/data, uploads/) por um bucket
S3-compatible, evitando perda de arquivos em deploys/restarts (filesystem
efemero do Railway).
"""
import logging
from typing import Optional

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from core.config import settings

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.STORAGE_ENDPOINT,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY_ID,
            aws_secret_access_key=settings.STORAGE_SECRET_ACCESS_KEY,
            region_name=settings.STORAGE_REGION,
            config=BotoConfig(s3={"addressing_style": "path"}),
        )
    return _client


def upload_bytes(key: str, content: bytes) -> None:
    """Envia bytes para o bucket sob a chave informada."""
    get_client().put_object(Bucket=settings.STORAGE_BUCKET, Key=key, Body=content)
    logger.info(f"Arquivo enviado ao storage: {key}")


def download_bytes(key: str) -> bytes:
    """Baixa o conteudo de um objeto do bucket."""
    response = get_client().get_object(Bucket=settings.STORAGE_BUCKET, Key=key)
    return response["Body"].read()


def file_exists(key: str) -> bool:
    """Verifica se um objeto existe no bucket."""
    try:
        get_client().head_object(Bucket=settings.STORAGE_BUCKET, Key=key)
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def get_file_size(key: str) -> Optional[int]:
    """Retorna o tamanho do objeto em bytes, ou None se nao existir."""
    try:
        response = get_client().head_object(Bucket=settings.STORAGE_BUCKET, Key=key)
        return response["ContentLength"]
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def delete_file(key: str) -> None:
    """Remove um objeto do bucket."""
    get_client().delete_object(Bucket=settings.STORAGE_BUCKET, Key=key)
    logger.info(f"Arquivo removido do storage: {key}")


def delete_prefix(prefix: str) -> None:
    """Remove todos os objetos sob um prefixo (equivalente a remover uma 'pasta')."""
    client = get_client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.STORAGE_BUCKET, Prefix=prefix):
        objetos = page.get("Contents", [])
        if not objetos:
            continue
        client.delete_objects(
            Bucket=settings.STORAGE_BUCKET,
            Delete={"Objects": [{"Key": obj["Key"]} for obj in objetos]},
        )
    logger.info(f"Arquivos removidos do storage com prefixo: {prefix}")
