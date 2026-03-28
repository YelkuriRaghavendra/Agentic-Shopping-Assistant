import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { importPKCS8, importJWK, SignJWT, type KeyLike } from 'jose';
import * as crypto from 'crypto';

/**
 * RequestSigningService — signs outbound UCP request bodies with our platform's
 * private key using a detached JWT (RFC 7797) via the `jose` library.
 *
 * The `Request-Signature` header value is a compact JWS with an empty payload
 * (detached content). The actual body hash is embedded in the JWT claims.
 */
@Injectable()
export class RequestSigningService implements OnModuleInit {
  private readonly logger = new Logger(RequestSigningService.name);
  private privateKey!: KeyLike;
  private keyId!: string;
  private algorithm!: string;

  constructor(private readonly config: ConfigService) {}

  async onModuleInit(): Promise<void> {
    await this.loadKey();
  }

  /**
   * Signs the request body and returns the `Request-Signature` header value.
   * Implements RFC 7797 detached content: the body hash is included in the JWT
   * payload, and the payload portion of the JWS is replaced with an empty string.
   *
   * @param body  Raw request body as a Buffer
   * @returns     The `Request-Signature` header value (detached JWS)
   */
  async signRequest(body: Buffer): Promise<string> {
    const bodyHash = crypto.createHash('sha256').update(body).digest('base64url');

    const jwt = await new SignJWT({ body_hash: bodyHash, body_hash_alg: 'sha-256' })
      .setProtectedHeader({ alg: this.algorithm, kid: this.keyId })
      .setIssuedAt()
      .setExpirationTime('5m')
      .sign(this.privateKey);

    // RFC 7797 detached content: replace the payload segment with an empty string
    const parts = jwt.split('.');
    if (parts.length !== 3) throw new Error('Unexpected JWT structure');
    return `${parts[0]}..${parts[2]}`;
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private async loadKey(): Promise<void> {
    this.keyId = this.config.get<string>('PLATFORM_SIGNING_KEY_ID', 'platform-key-1');
    this.algorithm = this.config.get<string>('PLATFORM_SIGNING_ALG', 'ES256');

    const jwkJson = this.config.get<string>('PLATFORM_SIGNING_KEY_JWK');
    const pkcs8Pem = this.config.get<string>('PLATFORM_SIGNING_KEY_PKCS8');

    if (jwkJson) {
      try {
        const jwk = JSON.parse(jwkJson);
        this.privateKey = (await importJWK(jwk, this.algorithm)) as KeyLike;
        this.logger.log(`Loaded platform signing key (JWK) kid=${this.keyId}`);
        return;
      } catch (err) {
        this.logger.error(`Failed to load platform signing key from JWK: ${err}`);
        throw err;
      }
    }

    if (pkcs8Pem) {
      try {
        this.privateKey = await importPKCS8(pkcs8Pem, this.algorithm);
        this.logger.log(`Loaded platform signing key (PKCS8) kid=${this.keyId}`);
        return;
      } catch (err) {
        this.logger.error(`Failed to load platform signing key from PKCS8: ${err}`);
        throw err;
      }
    }

    // Development fallback: generate an ephemeral key pair
    this.logger.warn(
      'No PLATFORM_SIGNING_KEY_JWK or PLATFORM_SIGNING_KEY_PKCS8 configured — ' +
        'generating ephemeral key pair (NOT suitable for production)',
    );
    const { privateKey } = await this.generateEphemeralKey();
    this.privateKey = privateKey;
  }

  private async generateEphemeralKey(): Promise<{ privateKey: KeyLike }> {
    const { generateKeyPair } = await import('jose');
    const { privateKey } = await generateKeyPair('ES256');
    return { privateKey };
  }
}
