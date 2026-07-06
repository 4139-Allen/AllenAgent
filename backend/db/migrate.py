"""
数据库迁移 — 建表 + 数据结构变更

开发阶段用 create_all，生产推荐 Alembic
"""

import sys
import logging
from pathlib import Path

# 确保 backend/ 在 sys.path 中
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from db.database import init_db, SessionLocal
from db.models import User

logger = logging.getLogger(__name__)


def _migrate_avatar_to_db():
    """将磁盘上的旧头像迁移到数据库（profile/avatars/avatar.* → users.avatar_data）"""
    avatar_paths = [
        backend_dir / "profile" / "avatars" / "avatar.jpg",
        backend_dir / "profile" / "avatars" / "avatar.png",
    ]
    existing = [p for p in avatar_paths if p.exists()]
    if not existing:
        logger.info("[迁移] 无旧头像文件需要迁移")
        return

    db = SessionLocal()
    try:
        # 找到第一个 admin 用户或 default 用户来挂载头像
        user = (
            db.query(User)
            .filter((User.role == "admin") | (User.id == "default"))
            .first()
        )
        if not user:
            # 取第一个用户
            user = db.query(User).first()

        if not user:
            logger.warning("[迁移] 无用户可挂载头像，跳过迁移")
            db.close()
            return

        if user.avatar_data is not None:
            logger.info("[迁移] 用户已有头像数据，跳过迁移")
            db.close()
            return

        avatar_file = existing[0]
        mime = "image/jpeg" if avatar_file.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        user.avatar_data = avatar_file.read_bytes()
        user.avatar_mime = mime
        db.commit()
        logger.info("[迁移] 旧头像已迁移到数据库（用户: %s, 大小: %d bytes）",
                     user.id, len(user.avatar_data))

        # 备份旧文件（不改名，不改动磁盘文件）
        logger.info("[迁移] 旧头像文件保留在 %s，可手动删除", avatar_file)
    except Exception as e:
        db.rollback()
        logger.error("[迁移] 头像迁移失败: %s", e)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("==> 创建/更新数据库表...")
    init_db()
    print("==> 迁移旧头像到数据库...")
    _migrate_avatar_to_db()
    print("==> 迁移完成")
