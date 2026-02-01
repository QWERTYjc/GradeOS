"""文件存储服务

支持多种存储后端：
1. 本地文件存储（开发环境）
2. AWS S3（生产环境）
3. 阿里云 OSS（可选）

Requirements:
- 持久化存储用户上传的原始文件（PDF/图片）
- 支持按 batch_id 组织文件
- 提供文件检索和下载功能
"""

import os
import io
import uuid
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StoredFile:
    """存储的文件信息"""
    file_id: str
    filename: str
    content_type: str
    size: int
    storage_path: str
    batch_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "storage_path": self.storage_path,
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class FileStorageBackend(ABC):
    """文件存储后端抽象基类"""
    
    @abstractmethod
    async def save(
        self,
        file_data: bytes,
        filename: str,
        batch_id: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredFile:
        """保存文件"""
        pass
    
    @abstractmethod
    async def get(self, file_id: str) -> Optional[bytes]:
        """获取文件内容"""
        pass
    
    @abstractmethod
    async def get_info(self, file_id: str) -> Optional[StoredFile]:
        """获取文件信息"""
        pass
    
    @abstractmethod
    async def delete(self, file_id: str) -> bool:
        """删除文件"""
        pass
    
    @abstractmethod
    async def list_by_batch(self, batch_id: str) -> List[StoredFile]:
        """列出批次下的所有文件"""
        pass


class LocalFileStorage(FileStorageBackend):
    """本地文件存储（开发环境）"""
    
    def __init__(self, base_path: str = "./uploads"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_path / "index.json"
        self._file_index: Dict[str, StoredFile] = {}
        self._load_index()
        logger.info(f"[FileStorage] 使用本地存储: {self.base_path.absolute()}")
    
    def _load_index(self):
        """加载文件索引"""
        if self.index_file.exists():
            try:
                import json
                with open(self.index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for file_id, info in data.items():
                        self._file_index[file_id] = StoredFile(**info)
                logger.info(f"[FileStorage] 已加载 {len(self._file_index)} 条文件索引")
            except Exception as e:
                logger.error(f"[FileStorage] 加载索引失败: {e}")
    
    def _save_index(self):
        """保存文件索引"""
        try:
            import json
            data = {fid: f.to_dict() for fid, f in self._file_index.items()}
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[FileStorage] 保存索引失败: {e}")

    def _generate_file_id(self, file_data: bytes, filename: str) -> str:
        """生成唯一文件 ID"""
        content_hash = hashlib.md5(file_data).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{timestamp}_{content_hash}_{uuid.uuid4().hex[:8]}"
    
    def _get_batch_path(self, batch_id: str) -> Path:
        """获取批次目录路径"""
        batch_path = self.base_path / batch_id
        batch_path.mkdir(parents=True, exist_ok=True)
        return batch_path
    
    async def save(
        self,
        file_data: bytes,
        filename: str,
        batch_id: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredFile:
        """保存文件到本地"""
        try:
            file_id = self._generate_file_id(file_data, filename)
            batch_path = self._get_batch_path(batch_id)
            
            # 保留原始文件扩展名
            ext = Path(filename).suffix or self._guess_extension(content_type)
            storage_filename = f"{file_id}{ext}"
            storage_path = batch_path / storage_filename
            
            # 写入文件
            with open(storage_path, "wb") as f:
                f.write(file_data)
            
            stored_file = StoredFile(
                file_id=file_id,
                filename=filename,
                content_type=content_type,
                size=len(file_data),
                storage_path=str(storage_path),
                batch_id=batch_id,
                metadata=metadata or {},
            )
            
            self._file_index[file_id] = stored_file
            self._save_index() # 持久化索引
            
            logger.info(f"[FileStorage] 保存文件: {filename} -> {storage_path} ({len(file_data)} bytes)")
            return stored_file
        except Exception as e:
            logger.error(f"[FileStorage] 本地保存失败: {e}")
            raise
    
    def _guess_extension(self, content_type: str) -> str:
        """根据 MIME 类型猜测扩展名"""
        mime_to_ext = {
            "application/pdf": ".pdf",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "text/plain": ".txt",
        }
        return mime_to_ext.get(content_type, "")
    
    async def get(self, file_id: str) -> Optional[bytes]:
        """获取文件内容"""
        stored_file = self._file_index.get(file_id)
        if not stored_file:
            return None
        
        storage_path = Path(stored_file.storage_path)
        if not storage_path.exists():
            return None
        
        with open(storage_path, "rb") as f:
            return f.read()
    
    async def get_info(self, file_id: str) -> Optional[StoredFile]:
        """获取文件信息"""
        return self._file_index.get(file_id)
    
    async def delete(self, file_id: str) -> bool:
        """删除文件"""
        stored_file = self._file_index.get(file_id)
        if not stored_file:
            return False
        
        storage_path = Path(stored_file.storage_path)
        if storage_path.exists():
            storage_path.unlink()
        
        del self._file_index[file_id]
        self._save_index() # 持久化索引
        
        logger.info(f"[FileStorage] 删除文件: {file_id}")
        return True
    
    async def list_by_batch(self, batch_id: str) -> List[StoredFile]:
        """列出批次下的所有文件"""
        return [f for f in self._file_index.values() if f.batch_id == batch_id]


class S3FileStorage(FileStorageBackend):
    """AWS S3 文件存储（生产环境）"""
    
    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.region = region
        self.access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")
        self._client = None
        self._file_index: Dict[str, StoredFile] = {}
        logger.info(f"[FileStorage] 使用 S3 存储: bucket={bucket_name}, region={region}")
    
    async def _get_client(self):
        """获取 S3 客户端"""
        if self._client is None:
            try:
                import aioboto3
                session = aioboto3.Session()
                self._client = await session.client(
                    "s3",
                    region_name=self.region,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    endpoint_url=self.endpoint_url,
                ).__aenter__()
            except ImportError:
                logger.error("[FileStorage] aioboto3 未安装，无法使用 S3 存储")
                raise ImportError("请安装 aioboto3: pip install aioboto3")
        return self._client
    
    def _generate_file_id(self, file_data: bytes, filename: str) -> str:
        """生成唯一文件 ID"""
        content_hash = hashlib.md5(file_data).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{timestamp}_{content_hash}_{uuid.uuid4().hex[:8]}"
    
    def _get_s3_key(self, batch_id: str, file_id: str, ext: str) -> str:
        """生成 S3 对象键"""
        return f"batches/{batch_id}/{file_id}{ext}"
    
    async def save(
        self,
        file_data: bytes,
        filename: str,
        batch_id: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredFile:
        """保存文件到 S3"""
        client = await self._get_client()
        file_id = self._generate_file_id(file_data, filename)
        ext = Path(filename).suffix or ""
        s3_key = self._get_s3_key(batch_id, file_id, ext)
        
        # 上传到 S3
        await client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=file_data,
            ContentType=content_type,
            Metadata={
                "original_filename": filename,
                "batch_id": batch_id,
                **(metadata or {}),
            },
        )
        
        stored_file = StoredFile(
            file_id=file_id,
            filename=filename,
            content_type=content_type,
            size=len(file_data),
            storage_path=f"s3://{self.bucket_name}/{s3_key}",
            batch_id=batch_id,
            metadata=metadata or {},
        )
        
        self._file_index[file_id] = stored_file
        logger.info(f"[FileStorage] 保存文件到 S3: {filename} -> {s3_key} ({len(file_data)} bytes)")
        
        return stored_file
    
    async def get(self, file_id: str) -> Optional[bytes]:
        """从 S3 获取文件内容"""
        stored_file = self._file_index.get(file_id)
        if not stored_file:
            return None
        
        client = await self._get_client()
        s3_key = stored_file.storage_path.replace(f"s3://{self.bucket_name}/", "")
        
        try:
            response = await client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return await response["Body"].read()
        except Exception as e:
            logger.error(f"[FileStorage] S3 获取文件失败: {e}")
            return None
    
    async def get_info(self, file_id: str) -> Optional[StoredFile]:
        """获取文件信息"""
        return self._file_index.get(file_id)
    
    async def delete(self, file_id: str) -> bool:
        """从 S3 删除文件"""
        stored_file = self._file_index.get(file_id)
        if not stored_file:
            return False
        
        client = await self._get_client()
        s3_key = stored_file.storage_path.replace(f"s3://{self.bucket_name}/", "")
        
        try:
            await client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            del self._file_index[file_id]
            logger.info(f"[FileStorage] S3 删除文件: {file_id}")
            return True
        except Exception as e:
            logger.error(f"[FileStorage] S3 删除文件失败: {e}")
            return False
    
    async def list_by_batch(self, batch_id: str) -> List[StoredFile]:
        """列出批次下的所有文件"""
        return [f for f in self._file_index.values() if f.batch_id == batch_id]


class FileStorageService:
    """文件存储服务（统一接口）"""
    
    def __init__(self, backend: Optional[FileStorageBackend] = None):
        if backend is None:
            backend = self._create_default_backend()
        self.backend = backend
    
    def _create_default_backend(self) -> FileStorageBackend:
        """根据环境变量创建默认存储后端"""
        storage_type = os.getenv("FILE_STORAGE_TYPE", "local").lower()
        
        if storage_type == "s3":
            bucket_name = os.getenv("S3_BUCKET_NAME")
            if not bucket_name:
                logger.warning("[FileStorage] S3_BUCKET_NAME 未设置，回退到本地存储")
                return LocalFileStorage()
            
            return S3FileStorage(
                bucket_name=bucket_name,
                region=os.getenv("AWS_REGION", "us-east-1"),
            )
        
        # 默认使用本地存储
        base_path = os.getenv("FILE_STORAGE_PATH", "./uploads")
        return LocalFileStorage(base_path=base_path)
    
    async def save_answer_files(
        self,
        batch_id: str,
        files: List[bytes],
        filenames: List[str],
    ) -> List[StoredFile]:
        """保存答题文件"""
        stored_files = []
        for index, (file_data, filename) in enumerate(zip(files, filenames)):
            content_type = self._guess_content_type(filename)
            stored_file = await self.backend.save(
                file_data=file_data,
                filename=filename,
                batch_id=batch_id,
                content_type=content_type,
                metadata={"type": "answer", "page_index": index},
            )
            stored_files.append(stored_file)
        return stored_files
    
    async def save_rubric_files(
        self,
        batch_id: str,
        files: List[bytes],
        filenames: List[str],
    ) -> List[StoredFile]:
        """保存评分标准文件"""
        stored_files = []
        for index, (file_data, filename) in enumerate(zip(files, filenames)):
            content_type = self._guess_content_type(filename)
            stored_file = await self.backend.save(
                file_data=file_data,
                filename=filename,
                batch_id=batch_id,
                content_type=content_type,
                metadata={"type": "rubric", "page_index": index},
            )
            stored_files.append(stored_file)
        return stored_files
    
    def _guess_content_type(self, filename: str) -> str:
        """根据文件名猜测 MIME 类型"""
        ext = Path(filename).suffix.lower()
        ext_to_mime = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".txt": "text/plain",
        }
        return ext_to_mime.get(ext, "application/octet-stream")
    
    async def get_file(self, file_id: str) -> Optional[bytes]:
        """获取文件内容"""
        return await self.backend.get(file_id)
    
    async def get_file_info(self, file_id: str) -> Optional[StoredFile]:
        """获取文件信息"""
        return await self.backend.get_info(file_id)
    
    async def list_batch_files(self, batch_id: str) -> List[StoredFile]:
        """列出批次的所有文件"""
        return await self.backend.list_by_batch(batch_id)
    
    async def delete_file(self, file_id: str) -> bool:
        """删除文件"""
        return await self.backend.delete(file_id)


# 全局文件存储服务实例
_file_storage_service: Optional[FileStorageService] = None


def get_file_storage_service() -> FileStorageService:
    """获取全局文件存储服务"""
    global _file_storage_service
    if _file_storage_service is None:
        _file_storage_service = FileStorageService()
    return _file_storage_service


async def init_file_storage() -> FileStorageService:
    """初始化文件存储服务"""
    global _file_storage_service
    _file_storage_service = FileStorageService()
    logger.info("[FileStorage] 文件存储服务已初始化")
    return _file_storage_service
