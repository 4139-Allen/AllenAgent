from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """已上传的文件信息"""
    name: str = Field(..., description="原始文件名")
    path: str = Field(..., description="服务端文件路径")
    type: str = Field(..., description="MIME 类型")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = Field(None)
    reasoning_effort: str | None = Field(None)
    files: list[FileInfo] = Field(default_factory=list, description="关联的已上传文件")
