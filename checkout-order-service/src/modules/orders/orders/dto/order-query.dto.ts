import { IsNotEmpty, IsOptional, IsString, IsInt, Min, Max } from 'class-validator'
import { Type, Transform } from 'class-transformer'

export class OrderQueryDto {
  // Accept both camelCase (customerId) and snake_case (customer_id) from Python clients
  @IsOptional()
  @IsString()
  customer_id?: string

  @IsString()
  @IsNotEmpty()
  @Transform(({ obj }) => obj.customerId ?? obj.customer_id)
  customerId: string

  @IsOptional()
  @IsString()
  cursor?: string

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number = 20
}
