"""Initial schema

Revision ID: 001
Create Date: 2024-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable uuid-ossp
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # customers
    op.create_table(
        "customers",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("external_id", sa.String(255), nullable=True, unique=True),
        sa.Column("email",       sa.String(255), nullable=True),
        sa.Column("name",        sa.String(255), nullable=True),
        sa.Column("phone",       sa.String(50),  nullable=True),
        sa.Column("profile",     postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status",      sa.String(20),  nullable=False, server_default="active"),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_customers_external_id", "customers", ["external_id"])
    op.create_index("idx_customers_email",       "customers", ["email"])
    op.create_index("idx_customers_status",      "customers", ["status"])

    # sessions
    op.create_table(
        "sessions",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("customer_id",   postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel",       sa.String(50),  nullable=False, server_default="web"),
        sa.Column("status",        sa.String(20),  nullable=False, server_default="active"),
        sa.Column("context",       postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens",  sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at",    sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("ended_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at",    sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_sessions_customer_id", "sessions", ["customer_id"])
    op.create_index("idx_sessions_status",      "sessions", ["status"])
    op.create_index("idx_sessions_updated_at",  "sessions", ["updated_at"])
    op.create_index(
        "idx_sessions_active_customer",
        "sessions", ["customer_id", "status"],
        postgresql_where=sa.text("status = 'active'"),
    )

    # messages
    op.create_table(
        "messages",
        sa.Column("id",               postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id",       postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role",             sa.String(20),  nullable=False),
        sa.Column("content",          sa.Text(),      nullable=False),
        sa.Column("intent",           sa.String(50),  nullable=True),
        sa.Column("guardrail_status", sa.String(20),  nullable=True),
        sa.Column("guardrail_reason", sa.String(255), nullable=True),
        sa.Column("cited_products",   postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("input_tokens",     sa.Integer(), nullable=True),
        sa.Column("output_tokens",    sa.Integer(), nullable=True),
        sa.Column("latency_ms",       sa.Integer(), nullable=True),
        sa.Column("llm_model",        sa.String(50), nullable=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_messages_session_id", "messages", ["session_id"])
    op.create_index("idx_messages_created_at", "messages", ["created_at"])
    op.create_index("idx_messages_intent",     "messages", ["intent"])
    op.create_index(
        "idx_messages_cited", "messages", ["cited_products"],
        postgresql_using="gin",
    )

    # session_feedback
    op.create_table(
        "session_feedback",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id",    postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("rating",        sa.SmallInteger(), nullable=False),
        sa.Column("comment",       sa.Text(),     nullable=True),
        sa.Column("feedback_type", sa.String(50), nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_session_feedback_rating", "session_feedback", ["rating"])
    op.create_index("idx_session_feedback_type",   "session_feedback", ["feedback_type"])


def downgrade() -> None:
    op.drop_table("session_feedback")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("customers")
