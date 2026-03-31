import { Injectable, Logger, InternalServerErrorException } from '@nestjs/common'
import { EntityManager } from 'typeorm'
import { randomUUID } from 'crypto'

export interface AuditWriteParams {
  orderId: string
  actor: string
  actionType:
    | 'order_created'
    | 'status_changed'
    | 'cancelled'
    | 'return_initiated'
    | 'adjustment_applied'
  beforeState: unknown | null
  afterState: unknown
  source: 'api' | 'webhook' | 'system'
  ipAddress?: string
}

/**
 * AuditService — append-only audit log writer.
 *
 * MUST always be called within an existing EntityManager transaction.
 * If the INSERT fails, the transaction rolls back and the caller receives a 500.
 * No UPDATE or DELETE is ever issued against orders.audit_log.
 */
@Injectable()
export class AuditService {
  private readonly logger = new Logger(AuditService.name)

  async write(em: EntityManager, params: AuditWriteParams): Promise<void> {
    const {
      orderId,
      actor,
      actionType,
      beforeState,
      afterState,
      source,
      ipAddress = null,
    } = params

    try {
      await em.query(
        `INSERT INTO orders.audit_log
           (audit_id, order_id, actor, action_type, before_state, after_state, source, ip_address, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8::inet, NOW())`,
        [
          randomUUID(),
          orderId,
          actor,
          actionType,
          beforeState !== null ? JSON.stringify(beforeState) : null,
          JSON.stringify(afterState),
          source,
          ipAddress,
        ],
      )
    } catch (err) {
      this.logger.error(
        JSON.stringify({
          event: 'audit_log.write_failed',
          orderId,
          actionType,
          error: (err as Error).message,
        }),
      )
      // Re-throw so the surrounding transaction rolls back (Requirement 19.5)
      throw new InternalServerErrorException('Audit log write failed; transaction rolled back')
    }
  }
}
