import { httpClient, type RequestConfig } from "./httpClient";

export const GET = <T>(url: string, config?: RequestConfig): Promise<T> =>
  httpClient.get<T>(url, config);

export const POST = <T>(
  url: string,
  body: unknown,
  config?: RequestConfig
): Promise<T> => httpClient.post<T>(url, body, config);
