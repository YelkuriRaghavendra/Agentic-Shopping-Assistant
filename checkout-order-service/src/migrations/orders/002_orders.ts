import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateOrders1000000011 implements MigrationInterface {
  name = 'CreateOrders1000000011';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      CREATE TABLE orders.orders (
        order_id      UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
        customer_id   UUID         NOT NULL REFERENCES public.customers(customer_id),
        checkout_id   UUID         REFERENCES checkout.checkout_sessions(session_id),
        merchant_id   VARCHAR(255) NOT NULL,
        ucp_order_id  VARCHAR(255) NOT NULL,
        permalink_url TEXT,
        status        VARCHAR(30)  NOT NULL DEFAULT 'processing',
        line_items    JSONB        NOT NULL DEFAULT '[]',
        fulfillment   JSONB        NOT NULL DEFAULT '{}',
        adjustments   JSONB        NOT NULL DEFAULT '[]',
        totals        JSONB        NOT NULL DEFAULT '{}',
        created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        created_by    TEXT         NOT NULL DEFAULT 'system',
        last_updated_by TEXT
      )
    `);

    await queryRunner.query(`
      CREATE INDEX idx_orders_customer_id ON orders.orders(customer_id)
    `);
    await queryRunner.query(`
      CREATE INDEX idx_orders_status ON orders.orders(status)
    `);
    await queryRunner.query(`
      CREATE INDEX idx_orders_created_at ON orders.orders(created_at DESC)
    `);
    await queryRunner.query(`
      CREATE INDEX idx_orders_customer_created ON orders.orders(customer_id, created_at DESC)
    `);
    await queryRunner.query(`
      CREATE UNIQUE INDEX idx_orders_ucp_order_id ON orders.orders(ucp_order_id)
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS orders.orders CASCADE`);
  }
}
