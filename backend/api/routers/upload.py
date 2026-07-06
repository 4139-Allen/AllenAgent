"""
文件上传接口

职责: 接收 multipart 文件上传，保存到服务端临时目录
"""

import logging
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

# 上传目录（backend/uploads/）
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
ALLOWED_TYPES = {
    # 图片
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    # 文档
    "text/plain": ".txt",
    "application/pdf": ".pdf",
    "text/csv": ".csv",
    "application/json": ".json",
    "text/markdown": ".md",
    "text/x-python": ".py",
    "text/javascript": ".js",
    "text/html": ".html",
    "text/css": ".css",
    "application/xml": ".xml",
    "application/x-yaml": ".yaml",
    "text/yaml": ".yaml",
}
# 最大文件大小：50MB
MAX_FILE_SIZE = 50 * 1024 * 1024


@router.post("/files")
async def upload_files(files: list[UploadFile] = File(...)):
    """批量上传文件，返回每个文件的服务端路径"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []

    for file in files:
        # 检查文件类型
        if file.content_type and file.content_type not in ALLOWED_TYPES and not file.content_type.startswith("image/"):
            raise HTTPException(400, f"不支持的文件类型: {file.content_type}")

        # 检查文件大小
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(400, f"文件过大: {file.filename} ({len(content) / 1024 / 1024:.1f}MB, 上限50MB)")

        # 生成唯一文件名
        ext = Path(file.filename).suffix if file.filename else ".bin"
        if file.content_type in ALLOWED_TYPES:
            ext = ALLOWED_TYPES[file.content_type]
        save_name = f"{timestamp}_{len(results)}{ext}"
        save_path = UPLOAD_DIR / save_name

        # 写入文件
        save_path.write_bytes(content)

        results.append({
            "name": file.filename or save_name,
            "path": str(save_path.resolve()),
            "size": len(content),
            "type": file.content_type or "application/octet-stream",
        })

        logger.info("[Upload] 已保存: %s (%d bytes)", file.filename, len(content))

    return {"files": results}
