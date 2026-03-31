import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';
import * as express from 'express';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    rawBody: true,
  });

  // Allow requests from the Frontend dev server and any localhost origin
  app.enableCors({
    origin: (origin, callback) => {
      // Allow requests with no origin (curl, Postman) and any localhost port
      if (!origin || origin.startsWith('http://localhost') || origin.startsWith('http://127.0.0.1')) {
        callback(null, true);
      } else {
        callback(new Error('Not allowed by CORS'));
      }
    },
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-Request-ID', 'request-signature'],
    credentials: true,
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
