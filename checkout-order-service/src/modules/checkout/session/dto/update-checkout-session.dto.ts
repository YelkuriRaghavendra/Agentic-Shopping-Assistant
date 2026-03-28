import { IsArray, IsOptional, ValidateNested, ArrayMinSize } from 'class-validator';
import { Type } from 'class-transformer';
import { LineItemDto, BuyerDto, ContextDto } from './create-checkout-session.dto';

export class UpdateCheckoutSessionDto {
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
