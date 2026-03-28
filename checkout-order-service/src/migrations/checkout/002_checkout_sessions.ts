import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateCheckoutSessions1000000002 implements MigrationInterface {
  name = 'CreateCheckoutSessions1000000002';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      CREATE TABLE checkout.checkout_sessions (
        session_id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
        customer_id         UUID         NOT NULL REFERENCES public.customers(customer_id),
        merchant_id         VARCHAR(255) NOT NULL,
        ucp_checkout_id     VARCHAR(255),
        ucp_status          VARCHAR(30)  NOT NULL DEFAULT 'incomplete',
        continue_url        TEXT,
        expires_at          TIMESTAMPTZ,
        line_items_snapshot JSONB        NOT NULL DEFAULT '[]',
        buyer_snapshot      JSONB,
        context_snapshot    JSONB,
        payment_handlers    JSONB,
        totals_snapshot     JSONB,
        ucp_order_id        VARCHAR(255),
        ucp_order_permalink TEXT,
        created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        created_by          TEXT         NOT NULL DEFAULT 'system',
        last_updated_by     TEXT
      )
    `);

    await queryRunner.query(`
      CREATE INDEX idx_checkout_sessions_customer_id
        ON checkout.checkout_sessions(customer_id)
    `);
    await queryRunner.query(`
      CREATE INDEX idx_checkout_sessions_ucp_status
        ON checkout.checkout_sessions(ucp_status)
    `);
    await queryRunner.query(`
      CREATE INDEX idx_checkout_sessions_expires_at
        ON checkout.checkout_sessions(expires_at)
        WHERE ucp_status NOT IN ('completed', 'canceled')
    `);
    await queryRunner.query(`
      CREATE UNIQUE INDEX idx_checkout_sessions_ucp_id
        ON checkout.checkout_sessions(ucp_checkout_id)
        WHERE ucp_checkout_id IS NOT NULL
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS checkout.checkout_sessions CASCADE`);
  }
}
