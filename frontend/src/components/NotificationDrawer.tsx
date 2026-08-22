import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowClockwise, CheckCircle, LinkSimple, X } from "@phosphor-icons/react";
import {
  getNotificationGroups,
  refreshNotificationGroup,
  saveNotificationGroups,
} from "../api";
import type { NotificationGroup } from "../types";
import { Button, EmptyState, ErrorState, Skeleton } from "./Common";

interface EditableGroup extends NotificationGroup {
  conversationId: string;
}

export function NotificationDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const drawerRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const [groups, setGroups] = useState<EditableGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await getNotificationGroups();
      setGroups(next.map((group) => ({ ...group, conversationId: "" })));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取钉钉群配置。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = window.requestAnimationFrame(() => {
      drawerRef.current?.querySelector<HTMLElement>("[data-drawer-close]")?.focus();
    });
    const keepFocusInside = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;
      const focusable = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [href], [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => element.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", keepFocusInside);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", keepFocusInside);
      previousFocusRef.current?.focus();
    };
  }, [open, onClose]);

  const update = (index: number, values: Partial<EditableGroup>) => {
    setGroups((current) => current.map((group, groupIndex) => (groupIndex === index ? { ...group, ...values } : group)));
  };

  const refresh = async () => {
    setLoading(true);
    setNotice("");
    setError("");
    try {
      await Promise.all(groups.map((group) => refreshNotificationGroup(group.shortId)));
      await load();
      setNotice("群名与验证状态已刷新。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "刷新失败，请稍后重试。");
      setLoading(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setNotice("");
    setError("");
    try {
      await saveNotificationGroups(groups);
      setGroups((current) => current.map((group) => ({ ...group, conversationId: "" })));
      setNotice("通知配置已保存，新绑定信息不会在页面回显。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="drawer-layer" role="presentation">
      <button className="drawer-scrim" onClick={onClose} aria-label="关闭通知设置" />
      <aside ref={drawerRef} className="drawer" role="dialog" aria-modal="true" aria-labelledby="notification-title">
        <header className="drawer__head">
          <div>
            <h2 id="notification-title">钉钉通知群</h2>
            <p>已绑定群显示钉钉验证结果，本机名称用于值守人员辨认。</p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭" data-drawer-close>
            <X size={22} aria-hidden="true" />
          </button>
        </header>

        <div className="drawer__toolbar">
          <Button tone="neutral" onClick={refresh} disabled={loading}>
            <ArrowClockwise size={18} aria-hidden="true" />
            刷新群名
          </Button>
          <span>{groups.filter((group) => group.enabled).length} 个群已开启</span>
        </div>

        <div className="drawer__content">
          {loading ? <Skeleton rows={5} /> : null}
          {error ? <ErrorState message={error} retry={load} /> : null}
          {!loading && !error && groups.length === 0 ? (
            <EmptyState title="尚未发现通知群" detail="先在本机完成钉钉绑定，然后刷新群名。" />
          ) : null}
          {!loading && !error
            ? groups.map((group, index) => (
                <section className="group-sheet" key={group.shortId}>
                  <header>
                    <div>
                      <strong>{group.officialName}</strong>
                      <span className={group.verified ? "verify verify--ok" : "verify"}>
                        {group.verified ? <CheckCircle size={16} weight="fill" aria-hidden="true" /> : null}
                        {group.verificationText || (group.verified ? "已验证" : "待验证")}
                      </span>
                    </div>
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={group.enabled}
                        onChange={(event) => update(index, { enabled: event.target.checked })}
                      />
                      <span aria-hidden="true" />
                      <em>{group.enabled ? "已开启" : "已关闭"}</em>
                    </label>
                  </header>
                  <dl className="group-sheet__identity">
                    <div>
                      <dt>群短编号</dt>
                      <dd>{group.shortId}</dd>
                    </div>
                    {group.source ? (
                      <div>
                        <dt>识别来源</dt>
                        <dd>{group.source}</dd>
                      </div>
                    ) : null}
                  </dl>
                  <label className="field">
                    <span>本机名称</span>
                    <input
                      value={group.localName}
                      onChange={(event) => update(index, { localName: event.target.value })}
                      placeholder="例如：一号楼整改群"
                    />
                  </label>
                  <details>
                    <summary>
                      <LinkSimple size={17} aria-hidden="true" />
                      重新绑定此群
                    </summary>
                    <label className="field">
                      <span>新会话 ID</span>
                      <input
                        value={group.conversationId}
                        onChange={(event) => update(index, { conversationId: event.target.value })}
                        placeholder="只在提交新绑定时填写"
                        autoComplete="off"
                      />
                      <small>为保护连接信息，已保存的会话 ID 不会回显。</small>
                    </label>
                  </details>
                </section>
              ))
            : null}
        </div>

        <footer className="drawer__foot">
          <span className="save-notice" role="status">{notice}</span>
          <Button tone="primary" busy={saving} onClick={save} disabled={loading || groups.length === 0}>
            保存通知设置
          </Button>
        </footer>
      </aside>
    </div>
  );
}
