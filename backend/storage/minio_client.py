import io
from minio import Minio
from minio.error import S3Error
from api.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_client: Minio = None


def get_minio() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def ensure_buckets():
    client = get_minio()
    for bucket in [
        settings.minio_bucket_raw,
        settings.minio_bucket_clean,
        settings.minio_bucket_curated,
    ]:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("minio_bucket_created", bucket=bucket)


def upload_file(bucket: str, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    client = get_minio()
    data_stream = io.BytesIO(data)
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=data_stream,
        length=len(data),
        content_type=content_type,
    )
    logger.info("minio_upload", bucket=bucket, object=object_name, size=len(data))
    return f"{bucket}/{object_name}"


def upload_text(bucket: str, object_name: str, text: str) -> str:
    return upload_file(bucket, object_name, text.encode("utf-8"), content_type="text/plain; charset=utf-8")


def upload_json(bucket: str, object_name: str, json_str: str) -> str:
    return upload_file(bucket, object_name, json_str.encode("utf-8"), content_type="application/json")


def download_file(bucket: str, object_name: str) -> bytes:
    client = get_minio()
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def download_text(bucket: str, object_name: str) -> str:
    return download_file(bucket, object_name).decode("utf-8")


def object_exists(bucket: str, object_name: str) -> bool:
    try:
        get_minio().stat_object(bucket, object_name)
        return True
    except S3Error:
        return False


def get_presigned_url(bucket: str, object_name: str, expires_hours: int = 1) -> str:
    from datetime import timedelta
    client = get_minio()
    try:
        return client.presigned_get_object(bucket, object_name, expires=timedelta(hours=expires_hours))
    except S3Error as e:
        logger.error("minio_presign_failed", bucket=bucket, object=object_name, error=str(e))
        return None
