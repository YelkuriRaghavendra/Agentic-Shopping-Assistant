import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateWebhookEvents1000000014 implements MigrationInterface {
  name = 'CreateWebhookEvents1000000014';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      CREATE TABLE orders.webhook_events (
        event_id           VARCHAR(255) PRIMARY KEY,
        merchant_id        VARCHAR(255) NOT NULL,
        event_type         VARCHAR(100) NOT NULL,
        payload            JSONB        NOT NULL,
        status             VARCHAR(20)  NOT NULL DEFAULT 'queued',
        signature_verified BOOLEAN      NOT NULL DEFAULT FALSE,
        processed_at       TIMESTAMPTZ,
        error              TEXT,
        created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
      )
    `);

    await queryRunner.query(`
      CREATE INDEX idx_webhook_events_status ON orders.webhook_events(status)
    `);
    await queryRunner.query(`
      CREATE INDEX idx_webhook_events_merchant ON orders.webhook_events(merchant_id)
    `);
    await queryRunner.query(`
      CREATE INDEX idx_webhook_events_created_at ON orders.webhook_events(created_at DESC)
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS orders.webhook_events CASCADE`);
  }
}
