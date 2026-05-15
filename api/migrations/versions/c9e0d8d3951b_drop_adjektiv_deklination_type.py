"""drop adjektiv_deklination type

Hard cutover: ADJEKTIV_DEKLINATION removed from SectionType enum. Adjective-ending
tests are now COMPLETION items with free-form text input + criterion grading.
Existing rows referencing ADJEKTIV_DEKLINATION can't load under the new schema,
so we drop submissions and assignments. No production users yet.

Revision ID: c9e0d8d3951b
Revises: 61837634b823
Create Date: 2026-05-14 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e0d8d3951b"
down_revision: Union[str, Sequence[str], None] = "61837634b823"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM assignment_submissions;")
    op.execute("DELETE FROM assignments;")


def downgrade() -> None:
    # Data deletion is non-reversible.
    pass
