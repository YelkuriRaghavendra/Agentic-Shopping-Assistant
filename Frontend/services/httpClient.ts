/**
 * httpClient — base abstraction for all HTTP calls.
 * Currently wired to mock responses; swap baseURL + fetch for real API.
 */

export interface RequestConfig {
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export interface HttpClient {
  get<T>(url: string, config?: RequestConfig): Promise<T>;
  post<T>(url: string, body: unknown, config?: RequestConfig): Promise<T>;
}

class MockHttpClient implements HttpClient {
  private readonly baseURL: string;

  constructor(baseURL = "/api") {
    this.baseURL = baseURL;
  }

  async get<T>(url: string, _config?: RequestConfig): Promise<T> {
    console.debug(`[GET] ${this.baseURL}${url}`);
    // In a real implementation: return fetch(`${this.baseURL}${url}`, { ...config }).then(r => r.json())
    throw new Error("GET not implemented in mock mode — use POST /chat");
  }

  async post<T>(url: string, body: unknown, _config?: RequestConfig): Promise<T> {
    console.debug(`[POST] ${this.baseURL}${url}`, body);
    // Delegates to mock handler — real impl would call fetch here
    return Promise.resolve(body as T);
  }
}

export const httpClient: HttpClient = new MockHttpClient();
