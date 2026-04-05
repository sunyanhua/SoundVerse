"""添加preset_prompts表

Revision ID: 20240405_add_preset_prompts
Revises:
Create Date: 2026-04-05 14:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers
revision = '20240405_add_preset_prompts'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 创建preset_prompts表
    op.create_table('preset_prompts',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('original_message_id', sa.String(36), nullable=True),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('emotion', sa.String(50), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('like_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('review_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['original_message_id'], ['chat_messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('idx_preset_prompts_user_id', 'preset_prompts', ['user_id'])
    op.create_index('idx_preset_prompts_category', 'preset_prompts', ['category'])
    op.create_index('idx_preset_prompts_review_status', 'preset_prompts', ['review_status'])
    op.create_index('idx_preset_prompts_created_at', 'preset_prompts', ['created_at'])


def downgrade():
    op.drop_table('preset_prompts')