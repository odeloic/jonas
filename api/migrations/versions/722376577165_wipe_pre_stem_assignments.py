"""wipe pre-stem assignments

Hard cutover: the ADJEKTIV_DEKLINATION question shape now requires an adjective stem
immediately before the ___ blank (enforced by Pydantic). Legacy rows that were generated
without that stem (e.g. "Nehmt die___Papiere mit!") cannot be loaded by the new validator,
so we drop submissions and assignments to start clean. No production users yet.

Revision ID: 722376577165
Revises: c4d8b1e7f2a9
Create Date: 2026-05-14 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "722376577165"
down_revision: Union[str, Sequence[str], None] = "c4d8b1e7f2a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM assignment_submissions;")
    op.execute("DELETE FROM assignments;")


def downgrade() -> None:
    # Data deletion is non-reversible.
    pass
