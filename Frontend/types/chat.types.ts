export type MessageRole = "user" | "bot";

export interface ProductSuggestion {
  id: string;
  name: string;
  price: string;
  image: string;
  rating: number;
  badge?: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  products?: ProductSuggestion[];
}

export interface SendMessagePayload {
  message: string;
  conversationId: string;
}

export interface ChatResponse {
  id: string;
  content: string;
  products?: ProductSuggestion[];
  timestamp: Date;
}
