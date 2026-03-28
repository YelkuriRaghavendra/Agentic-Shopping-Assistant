import { Controller, Get, Logger } from '@nestjs/common'
import { ConfigService } from '@nestjs/config'
import { RequestSigningService } from '../../ucp-client/signing/request-signing.service'

/**
 * PlatformProfileController — exposes our platform's UCP profile document.
 *
 * Merchants discover our webhook URL and public signing key from this endpoint.
 * Requirement 9.1
 */
@Controller()
export class PlatformProfileController {
  private readonly logger = new Logger(PlatformProfileController.name)

  constructor(
    private readonly config: ConfigService,
    private readonly signingService: RequestSigningService,
  ) {}

  @Get('.well-known/ucp')
  async getProfile(): Promise<Record<string, unknown>> {
    const platformBaseUrl = this.config
      .get<string>('PLATFORM_BASE_URL', 'http://localhost:3001')
      .replace(/\/$/, '')

    const webhookUrl = `${platformBaseUrl}/commerce/webhooks/ucp/orders`

    // Expose our public signing key so merchants can verify our request signatures
    const publicJwk = await this.getPublicSigningKey()

    return {
      capabilities: [
        {
          namespace: 'dev.ucp.shopping.order',
          version: '1.0',
          config: {
            webhook_url: webhookUrl,
          },
        },
      ],
      signing_keys: {
        keys: publicJwk ? [publicJwk] : [],
      },
    }
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private async getPublicSigningKey(): Promise<Record<string, unknown> | null> {
    try {
      // Derive the public key from the configured private key material
      const jwkJson = this.config.get<string>('PLATFORM_SIGNING_KEY_JWK')
      const keyId = this.config.get<string>('PLATFORM_SIGNING_KEY_ID', 'platform-key-1')
      const alg = this.config.get<string>('PLATFORM_SIGNING_ALG', 'ES256')

      if (jwkJson) {
        const { importJWK } = await import('jose')
        const privateJwk = JSON.parse(jwkJson)
        // Strip private key fields, keep public fields
        const { d, p, q, dp, dq, qi, ...publicFields } = privateJwk
        return { ...publicFields, kid: keyId, use: 'sig', alg }
      }

      const pkcs8Pem = this.config.get<string>('PLATFORM_SIGNING_KEY_PKCS8')
      if (pkcs8Pem) {
        const { createPublicKey } = await import('crypto')
        const pubKey = createPublicKey(pkcs8Pem)
        const pubJwk = pubKey.export({ format: 'jwk' }) as Record<string, unknown>
        return { ...pubJwk, kid: keyId, use: 'sig', alg }
      }

      this.logger.warn('No platform signing key configured — returning empty signing_keys')
      return null
    } catch (err) {
      this.logger.error(`Failed to derive public signing key: ${err}`)
      return null
    }
  }
}
