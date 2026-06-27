"""
图片处理工具
支持：视觉 API 描述 / OCR 提取文字 / 元信息降级
"""

from pathlib import Path
from tools.base import BaseTool
from schemas.tool import ToolResult

# 支持的图片格式
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff'}


class ImageTool(BaseTool):
    """
    图片处理工具
    读取图片，生成描述或提取文字
    """

    def __init__(self, vision_provider=None):
        """
        Args:
            vision_provider: 支持 vision 的 LLMProvider（如 GPT-4o）
        """
        super().__init__(
            name="read_image",
            description="读取图片文件，识别内容。支持 PNG/JPG/GIF/BMP/WEBP 格式。"
        )
        self.vision_provider = vision_provider

    def set_vision_provider(self, provider):
        """设置视觉模型（延迟绑定）"""
        self.vision_provider = provider

    def execute(self, filepath: str, **kwargs) -> ToolResult:
        path = Path(filepath)

        if not path.exists():
            return ToolResult(success=False, data=None, error=f"文件不存在: {filepath}", source="image")

        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            return ToolResult(success=False, data=None, error=f"不支持的格式: {path.suffix}", source="image")

        # 优先级：视觉 API > OCR > 元信息
        if self.vision_provider:
            return self._describe_with_vision(path)

        ocr_result = self._extract_with_ocr(path)
        if ocr_result:
            return ocr_result

        return self._get_metadata(path)

    def _describe_with_vision(self, path: Path) -> ToolResult:
        """用视觉模型描述图片"""
        try:
            import base64
            mime = self._get_mime(path)
            b64 = base64.b64encode(path.read_bytes()).decode()
            image_url = f"data:{mime};base64,{b64}"

            result = self.vision_provider.chat(
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请详细描述这张图片的内容，包括文字、物体、场景等所有可见信息。"},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }],
                temperature=0.1,
            )

            if result["success"]:
                return ToolResult(
                    success=True,
                    data={"filepath": str(path), "method": "vision", "description": result["content"]},
                    source="image",
                )
            return self._extract_with_ocr(path) or self._get_metadata(path)

        except Exception:
            return self._extract_with_ocr(path) or self._get_metadata(path)

    def _extract_with_ocr(self, path: Path) -> ToolResult | None:
        """OCR 提取图片中的文字"""
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(path)
            text = pytesseract.image_to_string(img, lang='chi_sim+eng')

            if text.strip():
                return ToolResult(
                    success=True,
                    data={"filepath": str(path), "method": "ocr", "text": text.strip()},
                    source="image",
                )
            return None

        except ImportError:
            return None
        except Exception:
            return None

    def _get_metadata(self, path: Path) -> ToolResult:
        """降级：只返回图片元信息"""
        try:
            from PIL import Image
            img = Image.open(path)
            info = {
                "filepath": str(path),
                "method": "metadata",
                "format": img.format,
                "size": f"{img.width}x{img.height}",
                "mode": img.mode,
            }
        except ImportError:
            info = {
                "filepath": str(path),
                "method": "metadata",
                "size_bytes": path.stat().st_size,
            }
        except Exception as e:
            info = {"filepath": str(path), "method": "metadata", "error": str(e)}

        return ToolResult(success=True, data=info, source="image")

    def _get_mime(self, path: Path) -> str:
        return {
            '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
        }.get(path.suffix.lower(), 'image/png')

    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "图片文件路径",
                },
            },
            "required": ["filepath"],
        }
