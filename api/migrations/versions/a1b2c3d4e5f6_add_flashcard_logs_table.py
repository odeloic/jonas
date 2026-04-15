"""add flashcard_logs table

Revision ID: a1b2c3d4e5f6
Revises: e4ebd9b6826a
Create Date: 2026-04-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e4ebd9b6826a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flashcard_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_chat_id', sa.String(length=64), nullable=False),
        sa.Column('vocabulary_item_id', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['vocabulary_item_id'], ['vocabulary_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_flashcard_logs_telegram_chat_id'), 'flashcard_logs', ['telegram_chat_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_flashcard_logs_telegram_chat_id'), table_name='flashcard_logs')
    op.drop_table('flashcard_logs')
