const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const commerceBaseUrl =
  process.env.NEXT_PUBLIC_COMMERCE_BASE_URL ?? "http://localhost:3001";

export const API_PREFIX = "/api/v1";

export const endpoints = {
  chat:             `${apiBaseUrl}${API_PREFIX}/chat`,
  chatStream:       `${apiBaseUrl}${API_PREFIX}/chat/stream`,
  createCustomer:   `${apiBaseUrl}${API_PREFIX}/chat/customers`,
  getCustomer:      (id: string) => `${apiBaseUrl}${API_PREFIX}/chat/customers/${id}`,
  customerSessions: (id: string) => `${apiBaseUrl}${API_PREFIX}/chat/customers/${id}/sessions`,
  createSession:    `${apiBaseUrl}${API_PREFIX}/chat/sessions`,
  getSession:       (id: string) => `${apiBaseUrl}${API_PREFIX}/chat/sessions/${id}`,
  endSession:       (id: string) => `${apiBaseUrl}${API_PREFIX}/chat/sessions/${id}/end`,
  sessionMessages:  (id: string) => `${apiBaseUrl}${API_PREFIX}/chat/sessions/${id}/messages`,
  messageFeedback:  (id: string) => `${apiBaseUrl}${API_PREFIX}/chat/messages/${id}/feedback`,
  orderDetail:      (id: string) => `${commerceBaseUrl}/commerce/orders/${id}`,
} as const;

export { apiBaseUrl };
