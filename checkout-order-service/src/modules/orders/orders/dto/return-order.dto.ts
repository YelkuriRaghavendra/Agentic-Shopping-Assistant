import { IsOptional, IsString, MaxLength } from 'class-validator'

export class ReturnOrderDto {
  @IsOptional()
  @IsString()
  @MaxLength(500)
  reason?: string

  @IsOptional()
  @IsString()
  customerId?: string
}
