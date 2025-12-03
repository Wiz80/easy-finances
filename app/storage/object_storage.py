"""
Object storage utilities for receipt images and documents.

Uses MinIO (S3-compatible) for all file storage operations.
"""

import hashlib
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from minio import Minio

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# MinIO client singleton
_minio_client: Minio | None = None


def get_minio_client() -> Minio:
    """
    Get or create MinIO client instance.
    
    Returns:
        MinIO client
    """
    global _minio_client
    
    if _minio_client is None:
        _minio_client = Minio(
            f"{settings.minio_host}:{settings.minio_port}",
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        logger.debug(
            "minio_client_initialized",
            host=settings.minio_host,
            port=settings.minio_port,
        )
    
    return _minio_client


def ensure_bucket() -> None:
    """Ensure the MinIO bucket exists."""
    client = get_minio_client()
    bucket_name = settings.minio_bucket_name
    
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        logger.info("minio_bucket_created", bucket=bucket_name)
    else:
        logger.debug("minio_bucket_exists", bucket=bucket_name)


def compute_file_hash(file_bytes: bytes) -> str:
    """
    Compute SHA256 hash of file bytes.
    
    Args:
        file_bytes: File content as bytes
        
    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(file_bytes).hexdigest()


def upload_file(
    file_bytes: bytes,
    filename: str,
    content_hash: str | None = None,
) -> str:
    """
    Upload file to MinIO and return URI.
    
    Args:
        file_bytes: File content
        filename: Original filename (used for extension and content type)
        content_hash: Optional pre-computed hash (will compute if not provided)
        
    Returns:
        MinIO object URI (s3://bucket/key format)
    """
    # Compute hash if not provided
    if content_hash is None:
        content_hash = compute_file_hash(file_bytes)
    
    ensure_bucket()
    client = get_minio_client()
    bucket_name = settings.minio_bucket_name
    
    # Extract extension and determine content type
    extension = Path(filename).suffix.lower() or ".bin"
    content_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
        ".bin": "application/octet-stream",
    }
    content_type = content_type_map.get(extension, "application/octet-stream")
    
    # Object key: use hash with extension
    object_key = f"receipts/{content_hash}{extension}"
    
    try:
        # Upload to MinIO
        client.put_object(
            bucket_name=bucket_name,
            object_name=object_key,
            data=BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=content_type,
        )
        
        logger.info(
            "file_uploaded",
            filename=filename,
            bucket=bucket_name,
            object_key=object_key,
            size_bytes=len(file_bytes),
            hash=content_hash[:16],
        )
        
        # Return S3-style URI
        return f"s3://{bucket_name}/{object_key}"
        
    except Exception as e:
        logger.error(
            "file_upload_failed",
            filename=filename,
            error=str(e),
            exc_info=True,
        )
        raise


def file_exists(content_hash: str) -> bool:
    """
    Check if a file with the given hash already exists in MinIO.
    
    Args:
        content_hash: SHA256 hash of the file
        
    Returns:
        True if file exists, False otherwise
    """
    try:
        client = get_minio_client()
        bucket_name = settings.minio_bucket_name
        
        # List objects with prefix
        prefix = f"receipts/{content_hash}"
        objects = list(client.list_objects(bucket_name, prefix=prefix))
        
        exists = len(objects) > 0
        
        if exists:
            logger.debug("file_exists_in_storage", hash=content_hash[:16])
        
        return exists
        
    except Exception as e:
        logger.error(
            "file_exists_check_failed",
            hash=content_hash[:16],
            error=str(e),
        )
        return False


def get_file_url(
    blob_uri: str,
    expires_seconds: int = 3600,
) -> str:
    """
    Get a presigned URL for accessing a file.
    
    Args:
        blob_uri: Storage URI (s3://bucket/key format)
        expires_seconds: URL expiration time in seconds
        
    Returns:
        Presigned URL
    """
    client = get_minio_client()
    
    # Parse s3://bucket/key
    parts = blob_uri.replace("s3://", "").split("/", 1)
    bucket_name = parts[0]
    object_key = parts[1] if len(parts) > 1 else ""
    
    url = client.presigned_get_object(
        bucket_name=bucket_name,
        object_name=object_key,
        expires=timedelta(seconds=expires_seconds),
    )
    
    logger.debug(
        "presigned_url_generated",
        bucket=bucket_name,
        key=object_key,
        expires_seconds=expires_seconds,
    )
    
    return url


def delete_file(blob_uri: str) -> bool:
    """
    Delete a file from MinIO.
    
    Args:
        blob_uri: Storage URI (s3://bucket/key format)
        
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        client = get_minio_client()
        
        # Parse s3://bucket/key
        parts = blob_uri.replace("s3://", "").split("/", 1)
        bucket_name = parts[0]
        object_key = parts[1] if len(parts) > 1 else ""
        
        client.remove_object(bucket_name, object_key)
        
        logger.info(
            "file_deleted",
            bucket=bucket_name,
            key=object_key,
        )
        
        return True
        
    except Exception as e:
        logger.error(
            "file_delete_failed",
            uri=blob_uri,
            error=str(e),
            exc_info=True,
        )
        return False


def get_file(blob_uri: str) -> bytes:
    """
    Download a file from MinIO.
    
    Args:
        blob_uri: Storage URI (s3://bucket/key format)
        
    Returns:
        File content as bytes
        
    Raises:
        Exception: If file not found or download fails
    """
    client = get_minio_client()
    
    # Parse s3://bucket/key
    parts = blob_uri.replace("s3://", "").split("/", 1)
    bucket_name = parts[0]
    object_key = parts[1] if len(parts) > 1 else ""
    
    try:
        response = client.get_object(bucket_name, object_key)
        data = response.read()
        response.close()
        response.release_conn()
        
        logger.debug(
            "file_downloaded",
            bucket=bucket_name,
            key=object_key,
            size_bytes=len(data),
        )
        
        return data
        
    except Exception as e:
        logger.error(
            "file_download_failed",
            uri=blob_uri,
            error=str(e),
            exc_info=True,
        )
        raise
