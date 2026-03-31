import { Injectable, Logger } from '@nestjs/common';
import { importJWK, compactVerify, decodeProtectedHeader } from 'jose';
import { MerchantProfileService, type JwkKey } from '../merchant-profile/merchant-profile.service';

/**
 * WebhookVerificationService — verifies inbound merchant webhook signatures.
 *
 * Algorithm (RFC 7797 detached JWT):
 *  1. Extract `Request-Signature` header (detached JWS: header..signature)
 *  2. Parse JWT protected header to get `kid`
 *  3. Fetch merchant JWK set via MerchantProfileService
 *  4. Find the key matching `kid`
 *  5. Re-attach the raw body as the JWT payload and verify the signature
 */
@Injectable()
export class WebhookVerificationService {
  private readonly logger = new Logger(WebhookVerificationService.name);

  constructor(private readonly merchantProfileService: MerchantProfileService) {}

  /**
   * Verifies a detached JWT webhook signature.
   *
   * @param merchantId  Merchant identifier (used to fetch signing keys)
   * @param signature   The `Request-Signature` header value (detached JWS)
   * @param rawBody     The raw request body as a Buffer
   * @returns           true if the signature is valid, false otherwise
   */
  async verifyWebhook(
    merchantId: string,
    signature: string,
    rawBody: Buffer,
  ): Promise<boolean> {
    try {
      // Parse the detached JWS: header..signature → header.payload.signature
      const parts = signature.split('.');
      if (parts.length !== 3 || parts[1] !== '') {
        this.logger.warn(`Invalid detached JWS format for merchant ${merchantId}`);
        return false;
      }

      // Decode the protected header to get the kid
      const header = decodeProtectedHeader(`${parts[0]}.e30.${parts[2]}`);
      const kid = header.kid;
      if (!kid) {
        this.logger.warn(`No kid in JWT header for merchant ${merchantId}`);
        return false;
      }

      // Fetch merchant signing keys
      const keys = await this.merchantProfileService.getSigningKeys(merchantId);
      const jwk = this.findKey(keys, kid);
      if (!jwk) {
        this.logger.warn(`No matching key kid=${kid} for merchant ${merchantId}`);
        return false;
      }

      const publicKey = await importJWK(jwk, header.alg as string);

      // Re-attach the raw body as the JWT payload (base64url-encoded)
      const bodyB64 = Buffer.from(rawBody).toString('base64url');
      const reattached = `${parts[0]}.${bodyB64}.${parts[2]}`;

      await compactVerify(reattached, publicKey);
      return true;
    } catch (err) {
      this.logger.warn(`Webhook signature verification failed for merchant ${merchantId}: ${err}`);
      return false;
    }
  }

  // ── Private ────────────────────────────────────────────────────────────────

  private findKey(keys: JwkKey[], kid: string): JwkKey | undefined {
    return keys.find((k) => k.kid === kid);
  }
}
