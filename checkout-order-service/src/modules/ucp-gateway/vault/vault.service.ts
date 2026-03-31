import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

/**
 * VaultService — fetches UCP credentials from HashiCorp Vault.
 * Falls back to environment variables when VAULT_ENABLED=false (local dev).
 */
@Injectable()
export class VaultService implements OnModuleInit {
  private readonly logger = new Logger(VaultService.name);
  private readonly vaultEnabled: boolean;
  private readonly vaultAddr: string;
  private readonly vaultToken: string;
  private readonly vaultSecretPath: string;

  // In-memory cache of secrets fetched from Vault
  private secrets: Record<string, string> = {};

  constructor(private readonly config: ConfigService) {
    this.vaultEnabled = config.get<string>('VAULT_ENABLED', 'false') === 'true';
    this.vaultAddr = config.get<string>('VAULT_ADDR', 'http://localhost:8200');
    this.vaultToken = config.get<string>('VAULT_TOKEN', '');
    this.vaultSecretPath = config.get<string>(
      'VAULT_SECRET_PATH',
      'secret/data/checkout-order-service',
    );
  }

  async onModuleInit(): Promise<void> {
    if (this.vaultEnabled) {
      await this.loadSecretsFromVault();
    } else {
      this.logger.log('Vault disabled — using environment variable fallback');
    }
  }

  /** Returns the UCP API key. */
  getUcpApiKey(): string {
    if (this.vaultEnabled) {
      return this.requireSecret('UCP_API_KEY');
    }
    return this.config.getOrThrow<string>('UCP_API_KEY');
  }

  /** Returns the HMAC secret used to verify inbound UCP webhook signatures. */
  getHmacSecret(): string {
    if (this.vaultEnabled) {
      return this.requireSecret('WEBHOOK_HMAC_SECRET');
    }
    return this.config.getOrThrow<string>('WEBHOOK_HMAC_SECRET');
  }

  /** Returns the UCP OAuth client secret. */
  getUcpOAuthClientSecret(): string {
    if (this.vaultEnabled) {
      return this.requireSecret('UCP_OAUTH_CLIENT_SECRET');
    }
    return this.config.getOrThrow<string>('UCP_OAUTH_CLIENT_SECRET');
  }

  // ── Private helpers ────────────────────────────────────────────────────────

  private requireSecret(key: string): string {
    const value = this.secrets[key];
    if (!value) {
      throw new Error(`Secret '${key}' not found in Vault cache`);
    }
    return value;
  }

  private async loadSecretsFromVault(): Promise<void> {
    try {
      const url = `${this.vaultAddr}/v1/${this.vaultSecretPath}`;
      const response = await fetch(url, {
        headers: { 'X-Vault-Token': this.vaultToken },
      });

      if (!response.ok) {
        throw new Error(`Vault responded with HTTP ${response.status}`);
      }

      const body = (await response.json()) as {
        data?: { data?: Record<string, string> };
      };
      const data = body?.data?.data ?? {};
      this.secrets = data;
      this.logger.log(`Loaded ${Object.keys(data).length} secrets from Vault`);
    } catch (err) {
      this.logger.error('Failed to load secrets from Vault', err);
      throw err;
    }
  }
}
