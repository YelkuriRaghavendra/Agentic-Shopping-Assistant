import { IsNotEmpty, IsOptional, IsString, IsInt, Min, Max } from 'class-validator'
import { Type } from 'class-transformer'

export class OrderQueryDto {
  @IsString()
  @IsNotEmpty()
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
