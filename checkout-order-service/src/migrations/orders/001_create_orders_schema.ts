import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateOrdersSchema1000000010 implements MigrationInterface {
  name = 'CreateOrdersSchema1000000010';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`CREATE SCHEMA IF NOT EXISTS orders`);
    await queryRunner.query(`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP SCHEMA IF EXISTS orders CASCADE`);
  }
}
