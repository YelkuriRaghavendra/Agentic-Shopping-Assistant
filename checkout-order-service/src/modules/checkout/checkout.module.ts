import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BullModule } from '@nestjs/bull';
import { CheckoutSession } from './session/checkout-session.entity';
import { CheckoutSessionService } from './session/checkout-session.service';
import { CheckoutController } from './session/checkout.controller';
import { UcpClientModule } from '../ucp-client/ucp-client.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([CheckoutSession]),
    BullModule.registerQueue({ name: 'order-events' }),
    UcpClientModule,
  ],
  controllers: [CheckoutController],
  providers: [CheckoutSessionService],
  exports: [CheckoutSessionService],
})
export class CheckoutModule {}
