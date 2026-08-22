import type {
  Detection,
  ImageDetectionResult,
  Incident,
  NotificationGroup,
  RiskLevel,
} from "./types";

const API_ROOT = import.meta.env.VITE_API_ROOT ?? "";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, init);
  } catch {
    throw new ApiError("无法连接本地服务，请确认后端已启动。", 0);
  }

  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json")
    ? await response.json().catch(() => ({}))
    : await response.text().catch(() => "");

  if (!response.ok) {
    const message =
      typeof body === "object" && body
        ? String(body.detail ?? body.message ?? `请求失败 (${response.status})`)
        : String(body || `请求失败 (${response.status})`);
    throw new ApiError(message, response.status);
  }
  return body as T;
}

function pick(source: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) {
    const value = source[key];
    if (value !== undefined && value !== null) return value;
  }
  return undefined;
}

export function mediaUrl(value: unknown): string | undefined {
  if (typeof value !== "string" || !value.trim()) return undefined;
  if (value.startsWith("data:") || value.startsWith("blob:") || /^https?:\/\//.test(value)) {
    return value;
  }
  if (value.startsWith("/")) return `${API_ROOT}${value}`;
  const looksLikeBase64 = value.length > 180 && !value.includes("\\") && !value.includes("/");
  if (looksLikeBase64) return `data:image/jpeg;base64,${value}`;
  return `${API_ROOT}/${value.replace(/^\.\//, "")}`;
}

export function normalizeRisk(value: unknown): RiskLevel {
  const text = String(value ?? "").toLowerCase();
  if (["red", "high", "danger", "critical", "红色", "高风险"].some((v) => text.includes(v))) return "red";
  if (["yellow", "medium", "warning", "黄色", "中风险"].some((v) => text.includes(v))) return "yellow";
  if (["safe", "normal", "neutral", "blue", "green", "正常", "合规"].some((v) => text.includes(v))) return "safe";
  return "unknown";
}

function normalizeBox(value: unknown): [number, number, number, number] | undefined {
  if (Array.isArray(value) && value.length >= 4) {
    const numbers = value.slice(0, 4).map(Number);
    if (numbers.every(Number.isFinite)) return numbers as [number, number, number, number];
  }
  if (value && typeof value === "object") {
    const box = value as Record<string, unknown>;
    const x1 = Number(pick(box, "x1", "left", "x"));
    const y1 = Number(pick(box, "y1", "top", "y"));
    const rawX2 = pick(box, "x2", "right");
    const rawY2 = pick(box, "y2", "bottom");
    const x2 = rawX2 === undefined ? x1 + Number(pick(box, "width", "w")) : Number(rawX2);
    const y2 = rawY2 === undefined ? y1 + Number(pick(box, "height", "h")) : Number(rawY2);
    if ([x1, y1, x2, y2].every(Number.isFinite)) return [x1, y1, x2, y2];
  }
  return undefined;
}

export function normalizeDetections(value: unknown): Detection[] {
  if (!Array.isArray(value)) return [];
  return value.map((item, index) => {
    const raw = (item ?? {}) as Record<string, unknown>;
    const label = String(pick(raw, "label", "class_name", "class", "name", "category") ?? "检测目标");
    const confidenceValue = Number(pick(raw, "confidence", "score", "conf"));
    return {
      id: String(pick(raw, "id", "detection_id") ?? `${label}-${index}`),
      label,
      confidence: Number.isFinite(confidenceValue) ? confidenceValue : undefined,
      risk: normalizeRisk(pick(raw, "risk", "risk_level", "alert_level", "level", "severity") ?? label),
      bbox: normalizeBox(pick(raw, "bbox", "box", "xyxy", "bounds")),
    };
  });
}

export function normalizeImageResult(payload: unknown): ImageDetectionResult {
  const raw = (payload ?? {}) as Record<string, unknown>;
  const result = ((raw.result ?? raw.data ?? raw) || {}) as Record<string, unknown>;
  const detections = normalizeDetections(pick(result, "detections", "objects", "boxes", "results"));
  let risk = normalizeRisk(pick(result, "risk", "risk_level", "level", "severity"));
  if (risk === "unknown") {
    risk = detections.some((item) => item.risk === "red")
      ? "red"
      : detections.some((item) => item.risk === "yellow")
        ? "yellow"
        : detections.length
          ? "safe"
          : "unknown";
  }
  const labels: Record<RiskLevel, string> = {
    red: "红色风险",
    yellow: "黄色风险",
    safe: "未发现违规",
    unknown: "等待人工复核",
  };
  return {
    id: pick(result, "record_id", "incident_id", "id") as string | number | undefined,
    source: String(pick(result, "source", "source_type") ?? "image"),
    risk,
    riskLabel: String(pick(result, "risk_label", "level_label") ?? labels[risk]),
    action: String(pick(result, "action", "next_action", "recommendation") ?? "核对检测目标并确认处置。"),
    originalUrl: mediaUrl(pick(result, "original_image_url", "original_url", "image_url", "source_image")),
    annotatedUrl: mediaUrl(pick(result, "annotated_image_url", "annotated_url", "result_image", "annotated_image")),
    width: Number(pick(result, "image_width", "width")) || undefined,
    height: Number(pick(result, "image_height", "height")) || undefined,
    detections,
    notification: (() => {
      const value = pick(result, "notification", "notification_result");
      if (!value || typeof value !== "object") return undefined;
      const notification = value as Record<string, unknown>;
      return {
        status: String(notification.status ?? ""),
        sentCount: Number(notification.sent_count ?? notification.sentCount ?? 0),
        message: String(notification.message ?? ""),
      };
    })(),
  };
}

function normalizeIncident(rawValue: unknown, index: number): Incident {
  const raw = (rawValue ?? {}) as Record<string, unknown>;
  const source = String(pick(raw, "source", "source_type") ?? "image");
  const risk = normalizeRisk(pick(raw, "risk", "risk_level", "level", "severity"));
  return {
    id: (pick(raw, "source_id", "id", "record_id", "incident_id") ?? index) as string | number,
    source,
    projectName: String(pick(raw, "project_name", "project", "site_name") ?? "未命名项目"),
    inspector: String(pick(raw, "inspector", "checker", "operator") ?? ""),
    risk,
    riskLabel: String(pick(raw, "risk_label", "level_label") ?? ({ red: "红色风险", yellow: "黄色风险", safe: "正常", unknown: "待复核" }[risk])),
    status: String(pick(raw, "incident_status", "status", "workflow_status") ?? "pending"),
    createdAt: String(pick(raw, "created_at", "detected_at", "timestamp", "time") ?? ""),
    imageUrl: mediaUrl(pick(raw, "image_url", "original_image_url", "thumbnail_url", "source_image", "evidence_url")),
    annotatedUrl: mediaUrl(pick(raw, "annotated_image_url", "annotated_url", "result_image", "evidence_url")),
    assignee: String(pick(raw, "assignee", "owner", "responsible_person") ?? ""),
    reviewer: String(pick(raw, "closed_by", "reviewer", "reviewed_by") ?? ""),
    dueDate: String(pick(raw, "due_at", "due_date", "deadline") ?? ""),
    notes: String(pick(raw, "resolution_note", "notes", "disposition", "remark") ?? ""),
    detections: normalizeDetections(pick(raw, "detections", "objects", "boxes")),
  };
}

export async function getBootstrap() {
  return request<Record<string, unknown>>("/api/bootstrap");
}

export async function saveContext(projectName: string, inspector: string) {
  return request<Record<string, unknown>>("/api/context", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_name: projectName, inspector }),
  });
}

export async function detectImage(file: File, projectName: string, inspector: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("project_name", projectName);
  form.append("inspector", inspector);
  const payload = await request<unknown>("/api/detect/image", { method: "POST", body: form });
  return normalizeImageResult(payload);
}

export async function detectRealtimeFrame(
  blob: Blob,
  sessionId: string,
  projectName: string,
  inspector: string,
) {
  const form = new FormData();
  form.append("file", blob, "realtime-frame.jpg");
  form.append("project_name", projectName);
  form.append("inspector", inspector);
  form.append("session", sessionId);
  form.append("confidence", "0.4");
  return request<Record<string, unknown>>("/api/realtime/frame", {
    method: "POST",
    body: form,
  });
}

export async function deleteRealtimeSession(sessionId: string) {
  await request<unknown>(`/api/realtime/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
}

export async function createVideoJob(file: File, projectName: string, inspector: string) {
  const form = new FormData();
  form.append("file", file);
  void projectName;
  void inspector;
  form.append("confidence", "0.4");
  return request<Record<string, unknown>>("/api/video/jobs", { method: "POST", body: form });
}

export async function getVideoJob(jobId: string) {
  return request<Record<string, unknown>>(`/api/video/jobs/${encodeURIComponent(jobId)}`);
}

export async function getIncidents(view: string, search: string, inspector: string) {
  const query = new URLSearchParams({ quick: view, search, inspector });
  const payload = await request<unknown>(`/api/incidents?${query}`);
  const raw = (payload ?? {}) as Record<string, unknown>;
  const list = Array.isArray(payload)
    ? payload
    : (raw.items ?? raw.records ?? raw.incidents ?? (raw.data as Record<string, unknown> | undefined)?.items ?? []);
  return Array.isArray(list) ? list.map(normalizeIncident) : [];
}

export async function updateIncident(source: string, id: string | number, values: Record<string, unknown>) {
  return request<unknown>(`/api/incidents/${encodeURIComponent(source)}/${encodeURIComponent(String(id))}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
}

export async function getStatistics() {
  return request<Record<string, unknown>>("/api/statistics");
}

export async function getNotificationGroups(): Promise<NotificationGroup[]> {
  const payload = await request<unknown>("/api/notifications/groups");
  const raw = (payload ?? {}) as Record<string, unknown>;
  const groups = Array.isArray(payload) ? payload : (raw.groups ?? raw.items ?? []);
  if (!Array.isArray(groups)) return [];
  return groups.map((item, index) => {
    const group = (item ?? {}) as Record<string, unknown>;
    const identity = ((group.identity ?? {}) || {}) as Record<string, unknown>;
    const identityStatus = String(pick(identity, "status") ?? "unavailable");
    const officialName = String(identity.official_name ?? "").trim();
    return {
      shortId: String(pick(group, "short_id", "shortId", "id") ?? `group-${index}`),
      officialName: officialName || String(pick(group, "official_name", "officialName", "name") ?? "未识别群"),
      localName: String(pick(group, "name", "local_name", "localName", "alias") ?? ""),
      enabled: Boolean(pick(group, "enabled", "active")),
      verified: identityStatus === "verified",
      verificationText: String(pick(identity, "reason") ?? identityStatus),
      source: String(pick(identity, "source") ?? ""),
    };
  });
}

export async function saveNotificationGroups(groups: Array<NotificationGroup & { conversationId?: string }>) {
  return request<unknown>("/api/notifications/groups", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      groups: groups.map((group) => ({
        short_id: group.shortId,
        name: group.localName || group.officialName,
        enabled: group.enabled,
        ...(group.conversationId ? { new_open_conversation_id: group.conversationId } : {}),
      })),
    }),
  });
}

export async function refreshNotificationGroup(shortId: string) {
  return request<unknown>(`/api/notifications/groups/${encodeURIComponent(shortId)}/refresh`, { method: "POST" });
}
