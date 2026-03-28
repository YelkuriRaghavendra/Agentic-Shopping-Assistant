import { IsNotEmpty, IsObject } from 'class-validator';

export class CompleteCheckoutSessionDto {
  @IsObject()
  @IsNotEmpty()
  payment_instrument: Record<string, unknown>;
}
