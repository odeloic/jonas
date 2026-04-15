"""add flashcard_sets table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-15 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flashcard_sets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_chat_id', sa.String(length=64), nullable=False),
        sa.Column('vocabulary_item_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_flashcard_sets_telegram_chat_id'), 'flashcard_sets', ['telegram_chat_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_flashcard_sets_telegram_chat_id'), table_name='flashcard_sets')
    op.drop_table('flashcard_sets')
