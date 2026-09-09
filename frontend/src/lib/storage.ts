export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Array<{
    title: string;
    resolution: string;
    article: string;
    source_type: string;
    excerpt: string;
  }>;
  durationSeconds?: number;
  trace?: any[];
  timestamp: string;
}

const STORAGE_KEY_CHAT = "can_i_graduate_ud_chat_history";
const STORAGE_KEY_TOKEN = "can_i_graduate_ud_admin_token";

export function getStoredChatHistory(): ChatMessage[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY_CHAT);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error("Error reading chat history from localStorage", e);
    return [];
  }
}

export function saveStoredChatHistory(messages: ChatMessage[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY_CHAT, JSON.stringify(messages));
  } catch (e) {
    console.error("Error saving chat history to localStorage", e);
  }
}

export function clearStoredChatHistory() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY_CHAT);
}

export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEY_TOKEN);
}

export function setAdminToken(token: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY_TOKEN, token);
}

export function clearAdminToken() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY_TOKEN);
}

