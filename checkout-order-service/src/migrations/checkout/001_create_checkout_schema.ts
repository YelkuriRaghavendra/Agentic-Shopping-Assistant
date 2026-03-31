import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateCheckoutSchema1700000000001 implements MigrationInterface {
  name = 'CreateCheckoutSchema1700000000001';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`CREATE SCHEMA IF NOT EXISTS checkout`);
    await queryRunner.query(`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP SCHEMA IF EXISTS checkout CASCADE`);
  }
}
