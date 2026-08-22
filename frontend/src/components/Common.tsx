import type { ButtonHTMLAttributes, ReactNode } from "react";
import { ArrowClockwise, ImageSquare, WarningCircle } from "@phosphor-icons/react";
import type { Detection, RiskLevel } from "../types";

export function Button({
  className = "",
  tone = "neutral",
  busy = false,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: "primary" | "neutral" | "danger" | "quiet";
  busy?: boolean;
}) {
  return (
    <button
      {...props}
      className={`button button--${tone} ${className}`}
      aria-busy={busy || undefined}
      disabled={busy || props.disabled}
    >
      {busy ? <span className="button__busy" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function PageTitle({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <header className="page-title">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action ? <div className="page-title__action">{action}</div> : null}
    </header>
  );
}

export function SectionHead({ title, detail, action }: { title: string; detail?: string; action?: ReactNode }) {
  return (
    <div className="section-head">
      <div>
        <h2>{title}</h2>
        {detail ? <p>{detail}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="state-message state-message--error" role="alert">
      <WarningCircle size={22} weight="bold" aria-hidden="true" />
      <div>
        <strong>当前操作未完成</strong>
        <p>{message}</p>
      </div>
      {retry ? (
        <Button tone="neutral" onClick={retry}>
          <ArrowClockwise size={18} aria-hidden="true" />
          重试
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <ImageSquare size={34} weight="thin" aria-hidden="true" />
      <h3>{title}</h3>
      <p>{detail}</p>
      {action}
    </div>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton" aria-label="正在加载">
      {Array.from({ length: rows }, (_, index) => (
        <span key={index} style={{ width: `${96 - index * 13}%` }} />
      ))}
    </div>
  );
}

const riskLabels: Record<RiskLevel, string> = {
  red: "红色风险",
  yellow: "黄色风险",
  safe: "未发现违规",
  unknown: "待人工复核",
};

export function RiskMark({ risk, label }: { risk: RiskLevel; label?: string }) {
  return <span className={`risk-mark risk-mark--${risk}`}>{label ?? riskLabels[risk]}</span>;
}

export function SourceMark({ source }: { source: string }) {
  const labels: Record<string, string> = { image: "图片", realtime: "实时", live: "实时", video: "视频" };
  return <span className="source-mark">{labels[source] ?? source}</span>;
}

export function DetectionOverlay({
  detections,
  selectedId,
  sourceWidth,
  sourceHeight,
}: {
  detections: Detection[];
  selectedId?: string;
  sourceWidth?: number;
  sourceHeight?: number;
}) {
  return (
    <div className="detection-overlay" aria-hidden="true">
      {detections
        .filter((item) => item.bbox && (!selectedId || item.id === selectedId))
        .map((item) => {
          const [x1, y1, x2, y2] = item.bbox!;
          const normalized = Math.max(x1, y1, x2, y2) <= 1;
          const width = normalized ? 1 : Math.max(1, sourceWidth ?? x2);
          const height = normalized ? 1 : Math.max(1, sourceHeight ?? y2);
          const style = {
            left: `${(x1 / width) * 100}%`,
            top: `${(y1 / height) * 100}%`,
            width: `${((x2 - x1) / width) * 100}%`,
            height: `${((y2 - y1) / height) * 100}%`,
          };
          return (
            <span key={item.id} className={`detection-box detection-box--${item.risk}`} style={style}>
              <span>{item.label}</span>
            </span>
          );
        })}
    </div>
  );
}

export function confidenceText(value?: number) {
  if (value === undefined) return "";
  const normalized = value <= 1 ? value * 100 : value;
  return `${Math.round(normalized)}%`;
}
