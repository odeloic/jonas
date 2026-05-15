"""wipe pre-structured assignments

Hard cutover: assignment item shapes changed to structured discrete fields
(blanks[] for criterion items, options[] for closed types with explicit is_correct,
tokens[] with index for REORDER). Legacy rows in the previous shape cannot be
loaded by the new Pydantic validators, so we drop submissions and assignments.
No production users yet.

Revision ID: 61837634b823
Revises: 722376577165
Create Date: 2026-05-14 17:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "61837634b823"
down_revision: Union[str, Sequence[str], None] = "722376577165"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM assignment_submissions;")
    op.execute("DELETE FROM assignments;")


def downgrade() -> None:
    # Data deletion is non-reversible.
    pass
