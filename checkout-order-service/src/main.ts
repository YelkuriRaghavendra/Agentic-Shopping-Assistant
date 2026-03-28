import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';
import * as express from 'express';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    // Capture raw body for webhook signature verification (Req 9.2)
    rawBody: true,
  });

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
    }),
  );

  // Controllers already include 'commerce' in their @Controller() paths,
  // so no global prefix is set here to avoid doubling up.
  // The /.well-known/ucp route uses @Controller() with no prefix.

  const port = process.env.PORT ?? 3001;
  await app.listen(port);
  console.log(`checkout-order-service running on port ${port}`);
}

bootstrap();
