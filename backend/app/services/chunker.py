"""文本切块服务。

把文件内容切成小块（chunk），为后续向量化做准备。

为什么要切块？
- 一整个文件太长，直接做向量化效果差（语义被稀释）
- 切成小块后，每块有明确的语义，搜索更精准
- 例：main.py 200行 → 切成 5 块，搜索"路由注册"能精准命中路由那一块

切块策略：
- 按行切割，每块约 chunk_size 个字符
- 相邻块重叠 overlap 个字符，防止关键信息被切断
- 空文件和太小的文件（< 10 字符）跳过

示例（chunk_size=100, overlap=20）：
  原文: [第1-100字符] [第101-200字符] [第201-300字符]
  块1:  [第1-100字符]
  块2:  [第81-180字符]     ← 和块1重叠了20字符
  块3:  [第161-260字符]    ← 和块2重叠了20字符
"""

import logging
import os

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.chunk import Chunk
from app.models.file import File

logger = logging.getLogger(__name__)

# 小于这个长度的文件不切块（太短没意义）
MIN_CONTENT_LENGTH = 10


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """把一段文本切成多个块。

    参数:
        text: 原始文本
        chunk_size: 每块的目标字符数
        overlap: 相邻块重叠的字符数

    返回:
        切块列表，每个元素是一个字符串

    切块逻辑：
    1. 按行分割文本
    2. 逐行累积，当累积长度 >= chunk_size 时，产出一个块
    3. 产出后回退 overlap 个字符，开始累积下一个块
    4. 最后剩余的文本作为最后一个块
    """
    if not text or len(text.strip()) < MIN_CONTENT_LENGTH:
        return []

    lines = text.split("\n")
    chunks = []
    current_chunk = ""  # 当前正在累积的块

    for line in lines:
        # 把当前行加入累积（保留换行符，因为代码的换行有意义）
        current_chunk += line + "\n"

        # 累积够了，产出一个块
        if len(current_chunk) >= chunk_size:
            chunks.append(current_chunk.strip())

            # 回退 overlap 个字符，作为下一个块的开头
            # 这样相邻块有重叠，防止关键信息被切断
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:]
            else:
                current_chunk = ""

    # 最后剩余的文本也算一个块（如果有内容的话）
    if current_chunk.strip():
        # 如果剩余太短且已经有块了，合并到最后一个块
        if chunks and len(current_chunk.strip()) < MIN_CONTENT_LENGTH:
            chunks[-1] += "\n" + current_chunk.strip()
        else:
            chunks.append(current_chunk.strip())

    return chunks


def chunk_file(filepath: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """读取文件并切块。

    参数:
        filepath: 文件路径
        chunk_size: 每块字符数（None 则读配置）
        overlap: 重叠字符数（None 则读配置）

    返回:
        切块列表
    """
    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    if not os.path.exists(filepath):
        logger.warning("File not found: %s", filepath)
        return []

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as e:
        logger.error("Failed to read file %s: %s", filepath, e)
        return []

    return chunk_text(content, chunk_size, overlap)


def chunk_workspace(db: Session, workspace_id: int) -> int:
    """对工作区的所有文件执行切块，结果存入 chunks 表。

    流程：
    1. 清空该工作区的旧切块（全量重建，简单可靠）
    2. 查询该工作区的所有文件
    3. 逐个文件读取 → 切块 → 写入数据库
    4. 返回总切块数

    参数:
        db: 数据库 session
        workspace_id: 工作区 ID

    返回:
        总切块数量
    """
    # 1. 清空旧的切块
    deleted = db.query(Chunk).filter(Chunk.workspace_id == workspace_id).delete()
    logger.info("Deleted %d old chunks for workspace %d", deleted, workspace_id)

    # 2. 查询所有文件
    files = db.query(File).filter(File.workspace_id == workspace_id).all()
    if not files:
        logger.info("No files to chunk for workspace %d", workspace_id)
        db.commit()
        return 0

    # 3. 逐个文件切块
    total_chunks = 0
    for file in files:
        chunks = chunk_file(file.filepath)
        for i, content in enumerate(chunks):
            chunk = Chunk(
                file_id=file.id,
                workspace_id=workspace_id,
                chunk_index=i,
                content=content,
                token_count=len(content) // 4,  # 粗略估算：平均4字符≈1个token
            )
            db.add(chunk)
        total_chunks += len(chunks)
        logger.info("Chunked file '%s' into %d chunks", file.filename, len(chunks))

    db.commit()
    logger.info("Workspace %d: total %d chunks from %d files",
                workspace_id, total_chunks, len(files))
    return total_chunks
