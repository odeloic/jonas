"""wipe pre-criterion assignments

Hard cutover: the assignment content JSONB shape changed (REORDER tokens, AdjektivDeklination
endings, criterion-based COMPLETION/FILL_IN_THE_BLANK). Legacy rows are not loadable by the
new pydantic validators, so we drop submissions and assignments to start clean. No production
users yet — acceptable per the cutover decision.

Revision ID: c4d8b1e7f2a9
Revises: b2c3d4e5f6a7
Create Date: 2026-05-13 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d8b1e7f2a9"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM assignment_submissions;")
    op.execute("DELETE FROM assignments;")


def downgrade() -> None:
    # Data deletion is non-reversible.
    pass
