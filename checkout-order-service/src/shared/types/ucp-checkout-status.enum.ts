export enum UcpCheckoutStatus {
  INCOMPLETE = 'incomplete',
  REQUIRES_ESCALATION = 'requires_escalation',
  READY_FOR_COMPLETE = 'ready_for_complete',
  COMPLETE_IN_PROGRESS = 'complete_in_progress',
  COMPLETED = 'completed',
  CANCELED = 'canceled',
  PAYMENT_FAILED = 'payment_failed',
}
