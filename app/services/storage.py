"""Object storage service for SeaweedFS S3 API operations."""

import io
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, BinaryIO, Optional

import aioboto3
from botocore.config import Config as BotoConfig

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Async S3-compatible storage service for SeaweedFS."""

    def __init__(self):
        self._session: Optional[aioboto3.Session] = None
        self._config = BotoConfig(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=30,
        )

    @property
    def session(self) -> aioboto3.Session:
        """Get or create aioboto3 session."""
        if self._session is None:
            self._session = aioboto3.Session()
        return self._session

    @asynccontextmanager
    async def _get_client(self):
        """Get S3 client context manager."""
        async with self.session.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=self._config,
        ) as client:
            yield client

    async def create_bucket(self, bucket_name: str) -> bool:
        """Create a bucket if it doesn't exist."""
        try:
            async with self._get_client() as client:
                await client.create_bucket(Bucket=bucket_name)
                logger.info(f"Created bucket: {bucket_name}")
                return True
        except client.exceptions.BucketAlreadyExists:
            logger.info(f"Bucket already exists: {bucket_name}")
            return True
        except client.exceptions.BucketAlreadyOwnedByYou:
            logger.info(f"Bucket already owned by you: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            return False

    async def bucket_exists(self, bucket_name: str) -> bool:
        """Check if bucket exists."""
        try:
            async with self._get_client() as client:
                await client.head_bucket(Bucket=bucket_name)
                return True
        except Exception:
            return False

    async def upload_file(
        self,
        bucket_name: str,
        key: str,
        file_obj: BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Upload a file to bucket."""
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            if metadata:
                extra_args["Metadata"] = metadata

            async with self._get_client() as client:
                await client.upload_fileobj(file_obj, bucket_name, key, ExtraArgs=extra_args)
                logger.info(f"Uploaded {key} to {bucket_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to upload {key} to {bucket_name}: {e}")
            return False

    async def upload_bytes(
        self,
        bucket_name: str,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Upload bytes to bucket."""
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            if metadata:
                extra_args["Metadata"] = metadata

            async with self._get_client() as client:
                await client.put_object(
                    Bucket=bucket_name,
                    Key=key,
                    Body=data,
                    **extra_args,
                )
                logger.info(f"Uploaded {key} to {bucket_name} ({len(data)} bytes)")
                return True
        except Exception as e:
            logger.error(f"Failed to upload {key} to {bucket_name}: {e}")
            return False

    async def download_file(self, bucket_name: str, key: str) -> Optional[bytes]:
        """Download a file from bucket as bytes."""
        try:
            async with self._get_client() as client:
                response = await client.get_object(Bucket=bucket_name, Key=key)
                async with response["Body"] as stream:
                    return await stream.read()
        except client.exceptions.NoSuchKey:
            logger.warning(f"File not found: {key} in {bucket_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to download {key} from {bucket_name}: {e}")
            return None

    async def download_fileobj(
        self, bucket_name: str, key: str, file_obj: BinaryIO
    ) -> bool:
        """Download a file to a file-like object."""
        try:
            async with self._get_client() as client:
                await client.download_fileobj(bucket_name, key, file_obj)
                return True
        except client.exceptions.NoSuchKey:
            logger.warning(f"File not found: {key} in {bucket_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to download {key} from {bucket_name}: {e}")
            return False

    async def delete_file(self, bucket_name: str, key: str) -> bool:
        """Delete a file from bucket."""
        try:
            async with self._get_client() as client:
                await client.delete_object(Bucket=bucket_name, Key=key)
                logger.info(f"Deleted {key} from {bucket_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete {key} from {bucket_name}: {e}")
            return False

    async def delete_files(self, bucket_name: str, keys: list[str]) -> bool:
        """Delete multiple files from bucket."""
        if not keys:
            return True
        try:
            async with self._get_client() as client:
                await client.delete_objects(
                    Bucket=bucket_name,
                    Delete={"Objects": [{"Key": k} for k in keys]},
                )
                logger.info(f"Deleted {len(keys)} files from {bucket_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete files from {bucket_name}: {e}")
            return False

    async def list_files(
        self, bucket_name: str, prefix: str = "", max_keys: int = 1000
    ) -> list[dict]:
        """List files in bucket with optional prefix."""
        try:
            async with self._get_client() as client:
                response = await client.list_objects_v2(
                    Bucket=bucket_name, Prefix=prefix, MaxKeys=max_keys
                )
                return response.get("Contents", [])
        except Exception as e:
            logger.error(f"Failed to list files in {bucket_name}: {e}")
            return []

    async def file_exists(self, bucket_name: str, key: str) -> bool:
        """Check if file exists in bucket."""
        try:
            async with self._get_client() as client:
                await client.head_object(Bucket=bucket_name, Key=key)
                return True
        except Exception:
            return False

    async def get_file_metadata(self, bucket_name: str, key: str) -> Optional[dict]:
        """Get file metadata."""
        try:
            async with self._get_client() as client:
                response = await client.head_object(Bucket=bucket_name, Key=key)
                return {
                    "content_length": response.get("ContentLength"),
                    "content_type": response.get("ContentType"),
                    "last_modified": response.get("LastModified"),
                    "etag": response.get("ETag"),
                    "metadata": response.get("Metadata", {}),
                }
        except Exception as e:
            logger.error(f"Failed to get metadata for {key} in {bucket_name}: {e}")
            return None

    async def generate_presigned_url(
        self, bucket_name: str, key: str, expiration: int = 3600
    ) -> Optional[str]:
        """Generate a presigned URL for file access."""
        try:
            async with self._get_client() as client:
                url = await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket_name, "Key": key},
                    ExpiresIn=expiration,
                )
                return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            return None

    async def initialize_buckets(self) -> bool:
        """Initialize all required buckets."""
        buckets = [
            settings.s3_bucket_documents,
            settings.s3_bucket_processed,
            settings.s3_bucket_embeddings,
        ]
        for bucket in buckets:
            if not await self.create_bucket(bucket):
                return False
        return True


# Global storage service instance
storage_service = StorageService()