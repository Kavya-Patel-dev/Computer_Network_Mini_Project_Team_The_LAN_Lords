"""Create the initial application tables without modifying existing tables."""
from alembic import op

from backend.app.models import Base

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create_all creates only missing objects. Existing production tables are not dropped.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Deliberately non-destructive. Rollback requires a separately reviewed migration.
    pass
