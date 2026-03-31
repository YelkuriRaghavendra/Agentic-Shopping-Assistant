import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddStripeColumnsToCheckoutSessions1700000000003 implements MigrationInterface {
  name = 'AddStripeColumnsToCheckoutSessions1700000000003';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      ALTER TABLE checkout.checkout_sessions
        ADD COLUMN stripe_payment_intent_id VARCHAR(255),
        ADD COLUMN stripe_client_secret TEXT
    `);
    await queryRunner.query(`
      CREATE UNIQUE INDEX idx_checkout_sessions_stripe_pi_id
        ON checkout.checkout_sessions(stripe_payment_intent_id)
        WHERE stripe_payment_intent_id IS NOT NULL
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP INDEX IF EXISTS checkout.idx_checkout_sessions_stripe_pi_id`);
    await queryRunner.query(`
      ALTER TABLE checkout.checkout_sessions
        DROP COLUMN IF EXISTS stripe_payment_intent_id,
        DROP COLUMN IF EXISTS stripe_client_secret
    `);
  }
}
