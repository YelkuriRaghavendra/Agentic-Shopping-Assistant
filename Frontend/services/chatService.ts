import { randomDelay, generateId } from "@/lib/utils";
import type {
  SendMessagePayload,
  ChatResponse,
  ProductSuggestion,
} from "@/types/chat.types";

// ---------------------------------------------------------------------------
// Mock product catalog
// ---------------------------------------------------------------------------

const MOCK_PRODUCTS: Record<string, ProductSuggestion[]> = {
  shoes: [
    {
      id: "p1",
      name: "Nike Air Max 270",
      price: "$129.99",
      image: "https://api.dicebear.com/7.x/shapes/svg?seed=shoe1",
      rating: 4.8,
      badge: "Best Seller",
    },
    {
      id: "p2",
      name: "Adidas Ultraboost 22",
      price: "$179.99",
      image: "https://api.dicebear.com/7.x/shapes/svg?seed=shoe2",
      rating: 4.7,
    },
    {
      id: "p3",
      name: "New Balance 574",
      price: "$89.99",
      image: "https://api.dicebear.com/7.x/shapes/svg?seed=shoe3",
      rating: 4.5,
      badge: "Sale",
    },
  ],
  headphones: [
    {
      id: "p4",
      name: "Sony WH-1000XM5",
      price: "$349.99",
      image: "https://api.dicebear.com/7.x/shapes/svg?seed=hp1",
      rating: 4.9,
      badge: "Top Pick",
    },
    {
      id: "p5",
      name: "Apple AirPods Pro",
      price: "$249.99",
      image: "https://api.dicebear.com/7.x/shapes/svg?seed=hp2",
      rating: 4.8,
    },
    {
      id: "p6",
      name: "Bose QuietComfort 45",
      price: "$279.99",
      image: "https://api.dicebear.com/7.x/shapes/svg?seed=hp3",
      rating: 4.7,
      badge: "Sale",
    },
  ],
  laptops: [
    {
      id: "p7",
      name: 'MacBook Pro 14"',
      price: "$1,999.99",
      image: "https://api.dicebear.com/7.x/shapes/svg?seed=lap1",
      rating: 4.9,
      badge: "New",
    },
    {
      id: "p8",
      name: "Dell XPS 15",
      price: "$1,499.99",
      image: "https://api.dicebear.com/7.x/shapes/svg?seed=lap2",
      rating: 4.7,
    },
  ],
  watches: [
    {
      id: "p9",
      name: "Apple Watch Series 9",
      price: "$399.99",
      image: "https://api.dicebear.com/7.x/shapes/svg?seed=watch1",
      rating: 4.8,
      badge: "New",
    },
    {
      id: "p10",
      name: "Samsung Galaxy Watch 6",
      price: "$299.99",
      image: "https://api.dicebear.com/7.x/shapes/svg?seed=watch2",
      rating: 4.6,
    },
  ],
};

// ---------------------------------------------------------------------------
// Mock response templates
// ---------------------------------------------------------------------------

interface MockTemplate {
  keywords: string[];
  response: string;
  category: keyof typeof MOCK_PRODUCTS;
}

const MOCK_TEMPLATES: MockTemplate[] = [
  {
    keywords: ["shoe", "shoes", "sneaker", "sneakers", "footwear", "boot", "boots"],
    response: "Here are some shoes you might like. I've picked the top-rated options across styles and budgets:",
    category: "shoes",
  },
  {
    keywords: ["headphone", "headphones", "earphone", "earbuds", "audio", "music", "sound"],
    response: "Check out these deals on headphones. These are our most popular picks right now:",
    category: "headphones",
  },
  {
    keywords: ["laptop", "computer", "macbook", "notebook", "pc"],
    response: "Here are some powerful laptops for you. Great for work and creativity:",
    category: "laptops",
  },
  {
    keywords: ["watch", "smartwatch", "wearable"],
    response: "Take a look at these smartwatches. Style meets functionality:",
    category: "watches",
  },
];

const FALLBACK_RESPONSES = [
  "I'm here to help you find the perfect product! Try asking about shoes, headphones, laptops, or watches.",
  "Great question! I can help you discover amazing deals. What category are you interested in?",
  "Let me help you shop smarter! Ask me about any product category and I'll find the best options for you.",
  "I specialize in finding great products for you. Try asking about electronics, footwear, or accessories!",
];

function detectCategory(message: string): MockTemplate | null {
  const lower = message.toLowerCase();
  return (
    MOCK_TEMPLATES.find((t) => t.keywords.some((kw) => lower.includes(kw))) ??
    null
  );
}

// ---------------------------------------------------------------------------
// Public service
// ---------------------------------------------------------------------------

export async function sendChatMessage(
  payload: SendMessagePayload
): Promise<ChatResponse> {
  // Simulate network latency
  await randomDelay(1000, 2000);

  const match = detectCategory(payload.message);

  if (match) {
    return {
      id: generateId(),
      content: match.response,
      products: MOCK_PRODUCTS[match.category],
      timestamp: new Date(),
    };
  }

  const fallback =
    FALLBACK_RESPONSES[Math.floor(Math.random() * FALLBACK_RESPONSES.length)];

  return {
    id: generateId(),
    content: fallback,
    timestamp: new Date(),
  };
}
