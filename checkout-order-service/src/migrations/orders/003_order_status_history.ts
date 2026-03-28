import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateOrderStatusHistory1000000012 implements MigrationInterface {
  name = 'CreateOrderStatusHistory1000000012';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      CREATE TABLE orders.order_status_history (
        history_id  UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
        order_id    UUID        NOT NULL REFERENCES orders.orders(order_id) ON DELETE CASCADE,
        from_status VARCHAR(30),
        to_status   VARCHAR(30) NOT NULL,
        source      VARCHAR(50) NOT NULL,
        actor       TEXT,
        note        TEXT,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    await queryRunner.query(`
      CREATE INDEX idx_order_status_history_order_id
        ON orders.order_status_history(order_id)
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS orders.order_status_history CASCADE`);
  }
}
