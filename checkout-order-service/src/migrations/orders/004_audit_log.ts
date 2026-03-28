import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateAuditLog1000000013 implements MigrationInterface {
  name = 'CreateAuditLog1000000013';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      CREATE TABLE orders.audit_log (
        audit_id     UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
        order_id     UUID        REFERENCES orders.orders(order_id),
        actor        TEXT        NOT NULL,
        action_type  VARCHAR(50) NOT NULL,
        before_state JSONB,
        after_state  JSONB       NOT NULL,
        source       VARCHAR(50) NOT NULL,
        ip_address   INET,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    await queryRunner.query(`
      CREATE INDEX idx_audit_log_order_id ON orders.audit_log(order_id)
    `);
    await queryRunner.query(`
      CREATE INDEX idx_audit_log_actor ON orders.audit_log(actor)
    `);
    await queryRunner.query(`
      CREATE INDEX idx_audit_log_created_at ON orders.audit_log(created_at DESC)
    `);

    // Enforce append-only: prevent UPDATE and DELETE
    await queryRunner.query(`
      CREATE RULE audit_log_no_update AS ON UPDATE TO orders.audit_log DO INSTEAD NOTHING
    `);
    await queryRunner.query(`
      CREATE RULE audit_log_no_delete AS ON DELETE TO orders.audit_log DO INSTEAD NOTHING
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS orders.audit_log CASCADE`);
  }
}
