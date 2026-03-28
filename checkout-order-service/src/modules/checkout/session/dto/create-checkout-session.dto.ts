import {
  IsArray,
  IsNotEmpty,
  IsOptional,
  IsString,
  ValidateNested,
  ArrayMinSize,
  IsNumber,
  IsPositive,
  IsEmail,
} from 'class-validator';
import { Type } from 'class-transformer';

export class LineItemItemDto {
  @IsString()
  @IsNotEmpty()
  id: string;

  @IsString()
  @IsNotEmpty()
  title: string;

  @IsNumber()
  @IsPositive()
  price: number; // cents
}

export class LineItemDto {
  @ValidateNested()
  @Type(() => LineItemItemDto)
  item: LineItemItemDto;

  @IsNumber()
  @IsPositive()
  quantity: number;
}

export class BuyerDto {
  @IsString()
  @IsNotEmpty()
  first_name: string;

  @IsString()
  @IsNotEmpty()
  last_name: string;

  @IsEmail()
  email: string;

  @IsOptional()
  @IsString()
  phone_number?: string;
}

export class ContextDto {
  @IsOptional()
  @IsString()
  address_country?: string;

  @IsOptional()
  @IsString()
  address_region?: string;

  @IsOptional()
  @IsString()
  postal_code?: string;
}

export class CreateCheckoutSessionDto {
  @IsString()
  @IsNotEmpty()
  merchant_id: string;

  @IsString()
  @IsNotEmpty()
  customer_id: string;

  @IsArray()
  @ArrayMinSize(1)
  @ValidateNested({ each: true })
  @Type(() => LineItemDto)
  line_items: LineItemDto[];

  @IsOptional()
  @ValidateNested()
  @Type(() => BuyerDto)
  buyer?: BuyerDto;

  @IsOptional()
  @ValidateNested()
  @Type(() => ContextDto)
  context?: ContextDto;
}
