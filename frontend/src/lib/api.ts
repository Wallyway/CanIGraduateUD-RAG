import { getAdminToken } from "./storage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getDeviceId(): string {
  if (typeof window === "undefined") return "server_ssr";
  let id = localStorage.getItem("ud_client_device_id");
  if (!id) {
    id = "dev_" + Math.random().toString(36).substring(2, 11) + "_" + Date.now().toString(36);
    localStorage.setItem("ud_client_device_id", id);
  }
  return id;
}

export function getClientMac(): string {
  if (typeof window === "undefined") return "00:00:00:00:00:00";
  let mac = localStorage.getItem("ud_client_mac");
  if (!mac) {
    const screenData = `${window.screen?.width || 1920}x${window.screen?.height || 1080}x${window.screen?.colorDepth || 24}`;
    const cores = navigator.hardwareConcurrency || 4;
    let hash = 0;
    const str = `${screenData}_${cores}_${navigator.userAgent}_${Date.now()}`;
    for (let i = 0; i < str.length; i++) {
      hash = (hash << 5) - hash + str.charCodeAt(i);
      hash |= 0;
    }
    const hex = (Math.abs(hash).toString(16) + "abcdef0123456789").substring(0, 12);
    mac = (hex.match(/.{1,2}/g) || ["00", "11", "22", "33", "44", "55"]).join(":").toUpperCase();
    localStorage.setItem("ud_client_mac", mac);
  }
  return mac;
}

function getAuthHeaders(): HeadersInit {
  const token = getAdminToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function streamChat(
  query: string,
  history: Array<{ role: string; content: string }>,
  onToken: (token: string) => void,
  onCitations: (citations: any[]) => void,
  onDone: () => void,
  onError: (err: any) => void
) {
  try {
    const response = await fetch(`${API_BASE}/api/v1/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Device-Id": getDeviceId(),
        "X-MAC-Address": getClientMac(),
      },
      body: JSON.stringify({ query, history }),
    });

    const isSse = (response.headers.get("content-type") || "").includes("text/event-stream");

    if (!response.ok && !isSse) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP error! status: ${response.status}`);
    }

    if (!response.body) {
      throw new Error("No readable stream in response");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";


    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data: ")) continue;
        const dataStr = trimmed.replace("data: ", "").trim();

        if (dataStr === "[DONE]") {
          onDone();
          return;
        }

        try {
          const parsed = JSON.parse(dataStr);
          if (parsed.type === "token" && parsed.content) {
            onToken(parsed.content);
          } else if (parsed.type === "citations" && parsed.citations) {
            onCitations(parsed.citations);
          }
        } catch (e) {
          // ignore parse failure on partial stream
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err);
  }
}

// Admin API calls
export async function loginAdmin(username: string, password: string) {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al iniciar sesión");
  }
  return res.json();
}

export async function checkAdminAuth() {
  const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: getAuthHeaders(),
  });
  return res.ok;
}

export async function getAdminEmails(statusFilter?: string) {
  const url = new URL(`${API_BASE}/api/v1/admin/emails`);
  if (statusFilter) url.searchParams.set("status", statusFilter);
  const res = await fetch(url.toString(), { headers: getAuthHeaders() });
  if (!res.ok) throw new Error("Error al obtener correos");
  return res.json();
}

export async function approveEmail(emailId: number) {
  const res = await fetch(`${API_BASE}/api/v1/admin/emails/${emailId}/approve`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al aprobar comunicado");
  return res.json();
}

export async function rejectEmail(emailId: number) {
  const res = await fetch(`${API_BASE}/api/v1/admin/emails/${emailId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al desechar comunicado");
  return res.json();
}

export async function deleteEmail(emailId: number) {
  return rejectEmail(emailId);
}

export async function getAdminStats() {
  const res = await fetch(`${API_BASE}/api/v1/admin/stats`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al obtener estadísticas");
  return res.json();
}

export async function toggleAutonomousMode(enabled: boolean) {
  const res = await fetch(`${API_BASE}/api/v1/admin/settings/autonomous-mode`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error("Error al cambiar modo autónomo");
  return res.json();
}

export async function uploadBatchTriageFiles(files: File[]) {
  const token = getAdminToken();
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file);
  });

  const res = await fetch(`${API_BASE}/api/v1/admin/emails/upload-batch`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || "Error al procesar los archivos en lote");
  }
  return res.json();
}

export async function getDocuments() {
  const res = await fetch(`${API_BASE}/api/v1/documents/`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al obtener documentos");
  return res.json();
}

export async function uploadDocument(formData: FormData) {
  const token = getAdminToken();
  const res = await fetch(`${API_BASE}/api/v1/documents/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Error al subir documento");
  }
  return res.json();
}

export async function createMarkdownDocument(payload: {
  title: string;
  content: string;
  resolution_number?: string;
  effective_date?: string;
  supersedes_id?: number | null;
  scan_file?: File | null;
}) {
  const token = getAdminToken();
  const authHeaders: Record<string, string> = {};
  if (token) {
    authHeaders["Authorization"] = `Bearer ${token}`;
  }

  let body: any;
  let headers: Record<string, string> = { ...authHeaders };

  if (payload.scan_file) {
    const fd = new FormData();
    fd.append("title", payload.title);
    fd.append("content", payload.content);
    if (payload.resolution_number) fd.append("resolution_number", payload.resolution_number);
    if (payload.effective_date) fd.append("effective_date", payload.effective_date);
    if (payload.supersedes_id) fd.append("supersedes_id", String(payload.supersedes_id));
    fd.append("scan_file", payload.scan_file);
    body = fd;
  } else {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(payload);
  }

  const res = await fetch(`${API_BASE}/api/v1/documents/create-markdown`, {
    method: "POST",
    headers,
    body,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Error al crear el documento en Markdown");
  }
  return res.json();
}

export async function createMarkdownEmail(payload: {
  subject: string;
  markdown_content: string;
  sender?: string;
  scan_file?: File | null;
}) {
  const token = getAdminToken();
  const authHeaders: Record<string, string> = {};
  if (token) {
    authHeaders["Authorization"] = `Bearer ${token}`;
  }

  let body: any;
  let headers: Record<string, string> = { ...authHeaders };

  if (payload.scan_file) {
    const fd = new FormData();
    fd.append("subject", payload.subject);
    fd.append("markdown_content", payload.markdown_content);
    if (payload.sender) fd.append("sender", payload.sender);
    fd.append("scan_file", payload.scan_file);
    body = fd;
  } else {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(payload);
  }

  const res = await fetch(`${API_BASE}/api/v1/admin/emails/create-markdown`, {
    method: "POST",
    headers,
    body,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Error al registrar el comunicado en Markdown");
  }
  return res.json();
}

export async function deleteDocument(docId: number) {
  const res = await fetch(`${API_BASE}/api/v1/documents/${docId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al eliminar documento");
  return res.json();
}

export async function getAdminAnalytics() {
  const res = await fetch(`${API_BASE}/api/v1/admin/analytics`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al obtener métricas analíticas");
  return res.json();
}

export async function updateEmailMetadata(emailId: number, payload: {
  subject?: string;
  sender?: string;
  triage_summary?: string;
  target_program?: string;
}) {
  const res = await fetch(`${API_BASE}/api/v1/admin/emails/${emailId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Error al actualizar metadatos del comunicado");
  return res.json();
}

export async function batchActionEmails(emailIds: number[], action: "approve" | "reject") {
  const res = await fetch(`${API_BASE}/api/v1/admin/emails/batch`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ email_ids: emailIds, action }),
  });
  if (!res.ok) throw new Error("Error al ejecutar acción en lote");
  return res.json();
}

export async function deprecateDocument(docId: number, payload?: {
  reason?: string;
  superseded_by_title?: string;
}) {
  const res = await fetch(`${API_BASE}/api/v1/documents/${docId}/deprecate`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) throw new Error("Error al derogar documento");
  return res.json();
}

export async function testSemanticSearch(query: string, limit = 5) {
  const res = await fetch(`${API_BASE}/api/v1/documents/test-search`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ query, limit }),
  });
  if (!res.ok) throw new Error("Error en la prueba de búsqueda semántica");
  return res.json();
}

export async function getAdminSettings() {
  const res = await fetch(`${API_BASE}/api/v1/admin/settings`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al obtener configuración");
  return res.json();
}

export async function updateAdminSettings(payload: {
  autonomous_mode?: boolean;
  autonomous_threshold?: number;
  require_ud_domain?: boolean;
  conflict_guardrail?: boolean;
}) {
  const res = await fetch(`${API_BASE}/api/v1/admin/settings`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Error al guardar configuración");
  return res.json();
}

export function getDocumentPdfUrl(docId: number) {
  return `${API_BASE}/api/v1/documents/${docId}/pdf`;
}

export function getDocumentScanUrl(docId: number) {
  return `${API_BASE}/api/v1/documents/${docId}/scan`;
}

export interface SessionFeedbackData {
  session_id?: string;
  user_email?: string;
  feedback_type?: string;
  rating?: number;
  comments: string;
  include_transcript?: boolean;
  messages?: any[];
}

export async function sendSessionFeedback(data: SessionFeedbackData) {
  const res = await fetch(`${API_BASE}/api/v1/chat/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Device-Id": getDeviceId(),
      "X-MAC-Address": getClientMac(),
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Error al registrar feedback");
  }
  return res.json();
}

export async function getSessionFeedbacks(limit: number = 50) {
  const res = await fetch(`${API_BASE}/api/v1/chat/feedbacks?limit=${limit}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al obtener feedbacks de sesión");
  return res.json();
}

export async function updateFeedbackStatus(feedbackId: number, status: string) {
  const res = await fetch(`${API_BASE}/api/v1/chat/feedbacks/${feedbackId}/status`, {
    method: "PATCH",
    headers: getAuthHeaders(),
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Error al actualizar estado del feedback");
  return res.json();
}

export async function deleteFeedback(feedbackId: number) {
  const res = await fetch(`${API_BASE}/api/v1/chat/feedbacks/${feedbackId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al eliminar feedback");
  return res.json();
}

export async function getSecurityPenalties() {
  const res = await fetch(`${API_BASE}/api/v1/admin/security/penalties`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Error al consultar penalizaciones de seguridad");
  return res.json();
}

export async function revokeSecurityPenalty(identifier: string) {
  const res = await fetch(`${API_BASE}/api/v1/admin/security/revoke`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ identifier }),
  });
  if (!res.ok) throw new Error("Error al levantar penalización");
  return res.json();
}




