/**
 * httpClient — fetch-based HTTP client for all API calls.
 */

export interface RequestConfig {
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export interface HttpClient {
  get<T>(url: string, config?: RequestConfig): Promise<T>;
  post<T>(url: string, body: unknown, config?: RequestConfig): Promise<T>;
  patch<T>(url: string, body: unknown, config?: RequestConfig): Promise<T>;
}

export class HttpError extends Error {
  constructor(public readonly status: number, public readonly body: string) {
    super(`HTTP ${status}: ${body}`);
  }
}

export class FetchHttpClient implements HttpClient {
  async get<T>(url: string, config?: RequestConfig): Promise<T> {
    const res = await fetch(url, {
      method: "GET",
      headers: { ...config?.headers },
      signal: config?.signal,
    });
    if (!res.ok) {
      const body = await res.text();
      throw new HttpError(res.status, body);
    }
    return res.json() as Promise<T>;
  }

  async post<T>(url: string, body: unknown, config?: RequestConfig): Promise<T> {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...config?.headers,
      },
      body: JSON.stringify(body),
      signal: config?.signal,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new HttpError(res.status, text);
    }
    return res.json() as Promise<T>;
  }

  async patch<T>(url: string, body: unknown, config?: RequestConfig): Promise<T> {
    const res = await fetch(url, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...config?.headers,
      },
      body: JSON.stringify(body),
      signal: config?.signal,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new HttpError(res.status, text);
    }
    return res.json() as Promise<T>;
  }
}

export const httpClient: HttpClient = new FetchHttpClient();
