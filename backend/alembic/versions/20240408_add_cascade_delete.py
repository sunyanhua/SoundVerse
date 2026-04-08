"""
添加级联删除约束

Revision ID: 20240408_cascade_delete
Revises: 20240405_add_preset_prompts
Create Date: 2024-04-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '20240408_cascade_delete'
down_revision = '20240405_add_preset_prompts'
branch_labels = None
depends_on = None


def upgrade():
    """
    升级数据库：添加级联删除约束
    """
    # 1. 修改 chat_messages 表的 audio_segment_id 外键，添加 ON DELETE SET NULL
    # 先删除旧的外键约束
    try:
        op.drop_constraint('chat_messages_ibfk_2', 'chat_messages', type_='foreignkey')
    except:
        # 如果约束名不同，尝试查找并删除
        pass

    # 创建新的外键约束，带 ON DELETE SET NULL
    op.create_foreign_key(
        'fk_chat_messages_audio_segment',
        'chat_messages',
        'audio_segments',
        ['audio_segment_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # 2. favorite_segments 表已经通过 SQLAlchemy 的 cascade 处理
    # 但为了数据库完整性，我们也添加外键级联删除
    try:
        op.drop_constraint('favorite_segments_ibfk_2', 'favorite_segments', type_='foreignkey')
    except:
        pass

    op.create_foreign_key(
        'fk_favorite_segments_segment',
        'favorite_segments',
        'audio_segments',
        ['segment_id'],
        ['id'],
        ondelete='CASCADE'
    )

    print("✅ 级联删除约束添加完成")


def downgrade():
    """
    降级数据库：移除级联删除约束
    """
    # 恢复 chat_messages 的外键（不带级联）
    try:
        op.drop_constraint('fk_chat_messages_audio_segment', 'chat_messages', type_='foreignkey')
    except:
        pass

    op.create_foreign_key(
        'chat_messages_ibfk_2',
        'chat_messages',
        'audio_segments',
        ['audio_segment_id'],
        ['id']
    )

    # 恢复 favorite_segments 的外键（不带级联）
    try:
        op.drop_constraint('fk_favorite_segments_segment', 'favorite_segments', type_='foreignkey')
    except:
        pass

    op.create_foreign_key(
        'favorite_segments_ibfk_2',
        'favorite_segments',
        'audio_segments',
        ['segment_id'],
        ['id']
    )

    print("✅ 级联删除约束已移除")
