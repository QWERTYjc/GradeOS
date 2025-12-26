"""对象存储服务

提供文件存储接口，支持本地文件系统和 S3/MinIO
"""

import os
import uuid
from typing import List
from pathlib import Path


class StorageError(Exception):
    """存储错误"""
    pass


class StorageService:
    """
    对象存储服务
    
    当前实现使用本地文件系统，可以轻松迁移到 S3/MinIO
    """
    
    def __init__(self, base_path: str = "./storage"):
        """
        初始化存储服务
        
        Args:
            base_path: 存储根目录
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    async def save_file(
        self,
        file_data: bytes,
        submission_id: str,
        file_index: int,
        extension: str = "png"
    ) -> str:
        """
        保存文件到存储
        
        Args:
            file_data: 文件字节数据
            submission_id: 提交 ID
            file_index: 文件索引（用于多页文档）
            extension: 文件扩展名
            
        Returns:
            文件路径（相对于存储根目录）
            
        Raises:
            StorageError: 保存失败时抛出
        """
        try:
            # 创建提交目录
            submission_dir = self.base_path / submission_id
            submission_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            filename = f"page_{file_index}.{extension}"
            file_path = submission_dir / filename
            
            # 写入文件
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            # 返回相对路径
            relative_path = str(file_path.relative_to(self.base_path))
            return relative_path
            
        except Exception as e:
            raise StorageError(f"保存文件失败: {str(e)}") from e
    
    async def save_files(
        self,
        files_data: List[bytes],
        submission_id: str,
        extension: str = "png"
    ) -> List[str]:
        """
        批量保存文件
        
        Args:
            files_data: 文件字节数据列表
            submission_id: 提交 ID
            extension: 文件扩展名
            
        Returns:
            文件路径列表
            
        Raises:
            StorageError: 保存失败时抛出
        """
        file_paths = []
        for index, file_data in enumerate(files_data):
            file_path = await self.save_file(
                file_data,
                submission_id,
                index,
                extension
            )
            file_paths.append(file_path)
        
        return file_paths
    
    async def get_file(self, file_path: str) -> bytes:
        """
        读取文件
        
        Args:
            file_path: 文件路径（相对于存储根目录）
            
        Returns:
            文件字节数据
            
        Raises:
            StorageError: 读取失败时抛出
        """
        try:
            full_path = self.base_path / file_path
            
            if not full_path.exists():
                raise StorageError(f"文件不存在: {file_path}")
            
            with open(full_path, "rb") as f:
                return f.read()
                
        except Exception as e:
            raise StorageError(f"读取文件失败: {str(e)}") from e
    
    async def delete_files(self, submission_id: str) -> bool:
        """
        删除提交的所有文件
        
        Args:
            submission_id: 提交 ID
            
        Returns:
            是否成功删除
        """
        try:
            submission_dir = self.base_path / submission_id
            
            if not submission_dir.exists():
                return False
            
            # 删除目录及其所有内容
            import shutil
            shutil.rmtree(submission_dir)
            
            return True
            
        except Exception as e:
            raise StorageError(f"删除文件失败: {str(e)}") from e
