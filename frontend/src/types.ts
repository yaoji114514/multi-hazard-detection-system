export type RouteId = "image" | "live" | "video" | "incidents" | "analytics";

export type RiskLevel = "red" | "yellow" | "safe" | "unknown";

export interface AppContext {
  projectName: string;
  inspector: string;
}

export interface Detection {
  id: string;
  label: string;
  confidence?: number;
  risk: RiskLevel;
  bbox?: [number, number, number, number];
}

export interface ImageDetectionResult {
  id?: string | number;
  source?: string;
  risk: RiskLevel;
  riskLabel: string;
  action?: string;
  originalUrl?: string;
  annotatedUrl?: string;
  width?: number;
  height?: number;
  detections: Detection[];
  notification?: {
    status?: string;
    sentCount?: number;
    message?: string;
  };
}

export interface Incident {
  id: string | number;
  source: string;
  projectName: string;
  inspector?: string;
  risk: RiskLevel;
  riskLabel: string;
  status: string;
  createdAt?: string;
  imageUrl?: string;
  annotatedUrl?: string;
  assignee?: string;
  reviewer?: string;
  dueDate?: string;
  notes?: string;
  detections?: Detection[];
}

export interface NotificationGroup {
  shortId: string;
  officialName: string;
  localName: string;
  enabled: boolean;
  verified: boolean;
  verificationText?: string;
  source?: string;
}
