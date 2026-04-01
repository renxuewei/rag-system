"""
File storage service
Uses MinIO to store original document files
"""

from typing import Optional, BinaryIO, List
from datetime import timedelta
import io
import logging

from minio import Minio
from minio.error import S3Error

from app.config import config

logger = logging.getLogger(__name__)


class StorageService:
    """File storage service"""
    
    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        bucket_name: str = None,
        secure: bool = False
    ):
        self.endpoint = endpoint or config.MINIO_ENDPOINT
        self.access_key = access_key or config.MINIO_ROOT_USER
        self.secret_key = secret_key or config.MINIO_ROOT_PASSWORD
        self.bucket_name = bucket_name or config.MINIO_BUCKET
        self.secure = secure
        
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize MinIO client"""
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )

            # Ensure bucket exists
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")

            logger.info(f"✅ MinIO connection successful: {self.endpoint}")
        except Exception as e:
            logger.warning(f"⚠️ MinIO connection failed: {e}")
            self.client = None
    
    def upload_file(
        self,
        object_name: str,
        file_data: BinaryIO,
        file_size: int,
        content_type: str = "application/octet-stream"
    ) -> bool:
        """
        Upload file
        Args:
            object_name: Object name (file path)
            file_data: File data
            file_size: File size
            content_type: Content type
        """
        if not self.client:
            logger.warning("MinIO not connected, skipping upload")
            return False

        try:
            self.client.put_object(
                self.bucket_name,
                object_name,
                file_data,
                file_size,
                content_type=content_type
            )

            logger.info(f"File upload successful: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"File upload failed: {e}")
            return False
    
    def upload_local_file(
        self,
        file_path: str,
        object_name: str = None
    ) -> bool:
        """
        Upload local file
        Args:
            file_path: Local file path
            object_name: Object name (use filename if not specified)
        """
        if not self.client:
            return False

        try:
            import os

            if not object_name:
                object_name = os.path.basename(file_path)

            self.client.fput_object(
                self.bucket_name,
                object_name,
                file_path
            )

            logger.info(f"Local file upload successful: {file_path} -> {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Local file upload failed: {e}")
            return False
    
    def download_file(self, object_name: str) -> Optional[bytes]:
        """
        Download file
        Args:
            object_name: Object name
        Returns:
            File data
        """
        if not self.client:
            return None

        try:
            response = self.client.get_object(
                self.bucket_name,
                object_name
            )

            data = response.read()
            response.close()
            response.release_conn()

            return data
        except S3Error as e:
            logger.error(f"File download failed: {e}")
            return None
    
    def download_to_file(
        self,
        object_name: str,
        file_path: str
    ) -> bool:
        """
        Download file to local
        Args:
            object_name: Object name
            file_path: Local file path
        """
        if not self.client:
            return False

        try:
            self.client.fget_object(
                self.bucket_name,
                object_name,
                file_path
            )
            return True
        except S3Error as e:
            logger.error(f"File download failed: {e}")
            return False
    
    def delete_file(self, object_name: str) -> bool:
        """
        Delete file
        Args:
            object_name: Object name
        """
        if not self.client:
            return False

        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"File deletion successful: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"File deletion failed: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> List[dict]:
        """
        List files
        Args:
            prefix: Prefix filter
        Returns:
            File list
        """
        if not self.client:
            return []

        try:
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=prefix
            )

            files = []
            for obj in objects:
                files.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "etag": obj.etag
                })

            return files
        except S3Error as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def get_file_url(
        self,
        object_name: str,
        expires: timedelta = timedelta(hours=1)
    ) -> Optional[str]:
        """
        Get file access URL (pre-signed)
        Args:
            object_name: Object name
            expires: Expiration time
        Returns:
            Access URL
        """
        if not self.client:
            return None

        try:
            url = self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=expires
            )
            return url
        except S3Error as e:
            logger.error(f"Failed to get file URL: {e}")
            return None
    
    def file_exists(self, object_name: str) -> bool:
        """
        Check if file exists
        Args:
            object_name: Object name
        """
        if not self.client:
            return False

        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False

    def is_connected(self) -> bool:
        """Check connection status"""
        return self.client is not None


# Singleton
storage_service = StorageService()
