import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowClockwise,
  CheckCircle,
  ImageSquare,
  MagnifyingGlass,
  NotePencil,
} from "@phosphor-icons/react";
import { getIncidents, updateIncident } from "../api";
import type { AppContext, Incident } from "../types";
import {
  Button,
  EmptyState,
  ErrorState,
  PageTitle,
  RiskMark,
  Skeleton,
  SourceMark,
} from "../components/Common";

const quickViews = [
  ["open", "全部待办"],
  ["in_progress", "处理中"],
  ["mine", "待我处理"],
  ["unassigned", "未分配"],
  ["red", "红色待办"],
  ["overdue", "已超期"],
  ["all", "全部记录"],
] as const;

const statusLabels: Record<string, string> = {
  pending: "待处理",
  in_progress: "处理中",
  closed: "已关闭",
  false_positive: "误报",
  not_applicable: "不适用",
};

function inputDate(value?: string) {
  if (!value) return "";
  return value.replace(" ", "T").slice(0, 16);
}

export function IncidentsPage({ context, params }: { context: AppContext; params: URLSearchParams }) {
  const [quick, setQuick] = useState(params.get("view") || "open");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<Incident[]>([]);
  const [selectedKey, setSelectedKey] = useState(params.get("focus") || "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState("");
  const [visibleCount, setVisibleCount] = useState(30);
  const [form, setForm] = useState({ status: "pending", assignee: "", dueAt: "", note: "", reviewer: context.inspector });

  useEffect(() => {
    const requestedView = params.get("view");
    const focus = params.get("focus");
    if (requestedView) setQuick(requestedView);
    if (focus) setSelectedKey(focus);
  }, [params]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await getIncidents(quick, search, context.inspector.trim());
      setItems(next);
      const focus = params.get("focus");
      const selectedExists = next.some((item) => `${item.source}:${item.id}` === selectedKey);
      const focusedExists = focus && next.some((item) => `${item.source}:${item.id}` === focus);
      if (focusedExists) setSelectedKey(focus!);
      else if (!selectedExists) setSelectedKey(next[0] ? `${next[0].source}:${next[0].id}` : "");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取检测记录。");
    } finally {
      setLoading(false);
    }
  }, [quick, search, context.inspector, params, selectedKey]);

  useEffect(() => {
    setVisibleCount(30);
    void load();
  }, [quick, search, context.inspector]);

  const selected = useMemo(
    () => items.find((item) => `${item.source}:${item.id}` === selectedKey),
    [items, selectedKey],
  );

  useEffect(() => {
    const selectedIndex = items.findIndex((item) => `${item.source}:${item.id}` === selectedKey);
    if (selectedIndex >= visibleCount) setVisibleCount(selectedIndex + 1);
  }, [items, selectedKey, visibleCount]);

  useEffect(() => {
    if (!selected) return;
    setForm({
      status: selected.status || "pending",
      assignee: selected.assignee || "",
      dueAt: inputDate(selected.dueDate),
      note: selected.notes || "",
      reviewer: selected.reviewer || context.inspector || "",
    });
    setSaved("");
  }, [selected, context.inspector]);

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    setSaved("");
    setError("");
    try {
      await updateIncident(selected.source, selected.id, {
        status: form.status,
        assignee: form.assignee.trim(),
        due_at: form.dueAt ? form.dueAt.replace("T", " ") + ":00" : null,
        resolution_note: form.note.trim(),
        operator: form.reviewer.trim() || context.inspector.trim(),
      });
      setSaved("处置状态已保存。");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "处置状态保存失败。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page page--incidents">
      <PageTitle
        title="检测记录"
        description="像翻阅现场联系表一样浏览证据，在右侧处置单完成认领、整改和复核。"
        action={
          <Button tone="neutral" onClick={() => void load()} disabled={loading}>
            <ArrowClockwise size={18} aria-hidden="true" />刷新队列
          </Button>
        }
      />

      <div className="queue-toolbar">
        <div className="quick-views" aria-label="快捷视图">
          {quickViews.map(([value, label]) => (
            <button
              key={value}
              className={quick === value ? "is-active" : ""}
              onClick={() => setQuick(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <form
          className="queue-search"
          onSubmit={(event) => {
            event.preventDefault();
            setSearch(searchInput.trim());
          }}
        >
          <MagnifyingGlass size={19} aria-hidden="true" />
          <input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="搜索项目、检查人、负责人或记录号"
            aria-label="搜索检测记录"
          />
          <button type="submit">搜索</button>
        </form>
      </div>

      {error ? <ErrorState message={error} retry={load} /> : null}

      <div className="incidents-layout">
        <section className="contact-sheet" aria-label="现场证据联系表">
          <header className="contact-sheet__head">
            <h2>{quickViews.find(([value]) => value === quick)?.[1] ?? "处置队列"}</h2>
            <span>{loading ? "正在读取" : `已显示 ${Math.min(items.length, visibleCount)} / ${items.length}`}</span>
          </header>

          {loading ? <Skeleton rows={6} /> : null}
          {!loading && items.length === 0 ? (
            <EmptyState title="这个视图暂时没有记录" detail="切换快捷视图，或从图片与实时检测生成新的现场证据。" />
          ) : null}

          <div className="contact-grid">
            {!loading ? items.slice(0, visibleCount).map((item) => {
              const key = `${item.source}:${item.id}`;
              return (
                <button
                  key={key}
                  className={`contact-card ${selectedKey === key ? "is-selected" : ""}`}
                  onClick={() => setSelectedKey(key)}
                  aria-pressed={selectedKey === key}
                >
                  <div className="contact-card__image">
                    {item.imageUrl || item.annotatedUrl ? (
                      <img src={item.imageUrl ?? item.annotatedUrl} alt={`${item.projectName} 的现场证据`} />
                    ) : (
                      <span><ImageSquare size={28} aria-hidden="true" />证据图待加载</span>
                    )}
                  </div>
                  <div className="contact-card__body">
                    <div><RiskMark risk={item.risk} /><SourceMark source={item.source} /></div>
                    <strong>{item.projectName}</strong>
                    <dl>
                      <div><dt>状态</dt><dd>{statusLabels[item.status] ?? item.status}</dd></div>
                      <div><dt>负责人</dt><dd>{item.assignee || "未分配"}</dd></div>
                    </dl>
                    <span className="contact-card__time">{item.createdAt || `记录 #${item.id}`}</span>
                  </div>
                </button>
              );
            }) : null}
          </div>
          {!loading && items.length > visibleCount ? (
            <Button className="load-more" tone="neutral" onClick={() => setVisibleCount((count) => count + 30)}>
              再加载 {Math.min(30, items.length - visibleCount)} 条
            </Button>
          ) : null}
        </section>

        <aside className="disposition-sheet" aria-label="隐患处置单">
          {selected ? (
            <>
              <header>
                <div>
                  <span>处置记录 {selected.source}:{selected.id}</span>
                  <h2>{selected.projectName}</h2>
                </div>
                <RiskMark risk={selected.risk} label={selected.riskLabel} />
              </header>

              <div className="disposition-evidence">
                {selected.annotatedUrl || selected.imageUrl ? (
                  <img src={selected.annotatedUrl ?? selected.imageUrl} alt={`${selected.projectName} 检测证据`} />
                ) : (
                  <EmptyState title="证据图不可用" detail="原始记录仍然保留，可继续填写处置结果。" />
                )}
              </div>

              <dl className="incident-facts">
                <div><dt>来源</dt><dd><SourceMark source={selected.source} /></dd></div>
                <div><dt>检查人</dt><dd>{selected.inspector || "未记录"}</dd></div>
                <div><dt>发现时间</dt><dd>{selected.createdAt || "未记录"}</dd></div>
                {selected.violationSummary ? <div><dt>风险明细</dt><dd>{selected.violationSummary}</dd></div> : null}
              </dl>

              <form
                className="disposition-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void save();
                }}
              >
                <div className="field-pair">
                  <label className="field">
                    <span>处置状态</span>
                    <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                      <option value="pending">待处理</option>
                      <option value="in_progress">处理中</option>
                      <option value="closed">已关闭</option>
                      <option value="false_positive">误报</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>负责人</span>
                    <input value={form.assignee} onChange={(event) => setForm({ ...form, assignee: event.target.value })} placeholder="填写负责人" />
                  </label>
                </div>
                <div className="field-pair">
                  <label className="field">
                    <span>整改期限</span>
                    <input type="datetime-local" value={form.dueAt} onChange={(event) => setForm({ ...form, dueAt: event.target.value })} />
                  </label>
                  <label className="field">
                    <span>复核人</span>
                    <input value={form.reviewer} onChange={(event) => setForm({ ...form, reviewer: event.target.value })} placeholder="关闭或误报时填写" />
                  </label>
                </div>
                <label className="field">
                  <span>处置说明</span>
                  <textarea value={form.note} onChange={(event) => setForm({ ...form, note: event.target.value })} placeholder="记录整改、复核或误报依据" rows={4} />
                </label>
                <div className="form-actions">
                  <span className="save-notice" role="status">{saved}</span>
                  <Button tone="primary" type="submit" busy={saving}>
                    <NotePencil size={19} aria-hidden="true" />保存处置单
                  </Button>
                </div>
              </form>
            </>
          ) : (
            <EmptyState title="选择一张现场证据" detail="左侧联系表会驱动这里的证据和处置单。" />
          )}
        </aside>
      </div>
    </div>
  );
}
