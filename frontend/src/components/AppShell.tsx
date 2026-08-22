import { useEffect, useState, type ReactNode } from "react";
import {
  BellSimple,
  Camera,
  ChartBar,
  CheckCircle,
  ImageSquare,
  ListChecks,
  VideoCamera,
  WarningCircle,
} from "@phosphor-icons/react";
import { getBootstrap, saveContext } from "../api";
import { navigate } from "../router";
import type { AppContext, RouteId } from "../types";
import { NotificationDrawer } from "./NotificationDrawer";

const navItems: Array<{ id: RouteId; label: string; icon: typeof ImageSquare }> = [
  { id: "image", label: "隐患检测", icon: ImageSquare },
  { id: "live", label: "实时检测", icon: Camera },
  { id: "video", label: "视频检测", icon: VideoCamera },
  { id: "incidents", label: "检测记录", icon: ListChecks },
  { id: "analytics", label: "统计分析", icon: ChartBar },
];

export function AppShell({
  route,
  context,
  onContextChange,
  children,
}: {
  route: RouteId;
  context: AppContext;
  onContextChange: (context: AppContext) => void;
  children: ReactNode;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [system, setSystem] = useState<{ model: string; notifications: string; connected: boolean }>({
    model: "正在确认",
    notifications: "正在确认",
    connected: true,
  });

  useEffect(() => {
    let active = true;
    getBootstrap()
      .then((payload) => {
        if (!active) return;
        const modelState = ((payload.model ?? {}) || {}) as Record<string, unknown>;
        const notificationState = ((payload.notifications ?? {}) || {}) as Record<string, unknown>;
        const savedContext = ((payload.context ?? {}) || {}) as Record<string, unknown>;
        const model = modelState.status === "ready" && !modelState.fallback
          ? "模型可用"
          : modelState.fallback
            ? "模型已降级"
            : "模型需检查";
        const notificationCount = Number(notificationState.enabled ?? 0);
        const notificationText = String(
          notificationCount ? `${notificationCount} 个群开启` : "通知未开启",
        );
        setSystem({ model, notifications: notificationText, connected: true });
        if (!context.projectName && !context.inspector) {
          onContextChange({
            projectName: String(savedContext.project_name ?? ""),
            inspector: String(savedContext.inspector ?? ""),
          });
        }
      })
      .catch(() => {
        if (active) setSystem({ model: "服务未连接", notifications: "等待后端", connected: false });
      });
    return () => {
      active = false;
    };
  }, []);

  const persistContext = () => {
    void saveContext(context.projectName.trim(), context.inspector.trim()).catch(() => undefined);
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => navigate("image")} aria-label="返回隐患检测">
          <strong>现场安全签派台</strong>
          <span>影像校验与闭环处置</span>
        </button>

        <nav className="primary-nav" aria-label="主要功能">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={route === item.id ? "is-active" : ""}
                aria-current={route === item.id ? "page" : undefined}
                onClick={() => navigate(item.id)}
              >
                <Icon size={19} weight={route === item.id ? "fill" : "regular"} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="context-strip">
          <label>
            <span>项目</span>
            <input
              value={context.projectName}
              onChange={(event) => onContextChange({ ...context, projectName: event.target.value })}
              onBlur={persistContext}
              placeholder="填写项目"
              aria-label="项目名称"
            />
          </label>
          <label>
            <span>检查人</span>
            <input
              value={context.inspector}
              onChange={(event) => onContextChange({ ...context, inspector: event.target.value })}
              onBlur={persistContext}
              placeholder="填写姓名"
              aria-label="检查人"
            />
          </label>
          <div className={`system-summary ${system.connected ? "" : "system-summary--error"}`}>
            {system.connected ? (
              <CheckCircle size={18} weight="fill" aria-hidden="true" />
            ) : (
              <WarningCircle size={18} weight="fill" aria-hidden="true" />
            )}
            <span>{system.model}</span>
          </div>
          <button
            className="notification-trigger"
            onClick={() => setDrawerOpen(true)}
            aria-label={`通知设置，${system.notifications}`}
          >
            <BellSimple size={20} aria-hidden="true" />
            <span>{system.notifications}</span>
          </button>
        </div>
      </header>

      <main>{children}</main>
      <NotificationDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}
