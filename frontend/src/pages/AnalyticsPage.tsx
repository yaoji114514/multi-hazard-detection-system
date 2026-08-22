import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, ChartLine, ListMagnifyingGlass } from "@phosphor-icons/react";
import { getStatistics } from "../api";
import { navigate } from "../router";
import { Button, EmptyState, ErrorState, PageTitle, SectionHead, Skeleton } from "../components/Common";

interface DailyPoint {
  date: string;
  checks: number;
  violations: number;
}

interface RankingItem {
  key: string;
  label: string;
  count: number;
}

export function AnalyticsPage() {
  const [data, setData] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await getStatistics());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取统计数据。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const workflow = ((data.workflow ?? {}) || {}) as Record<string, unknown>;
  const checks = ((data.checks ?? {}) || {}) as Record<string, unknown>;
  const daily = (Array.isArray(data.daily) ? data.daily : []).map((value) => {
    const item = value as Record<string, unknown>;
    return {
      date: String(item.date ?? ""),
      checks: Number(item.checks ?? 0),
      violations: Number(item.violations ?? 0),
    } satisfies DailyPoint;
  }).reverse();
  const ranking = (Array.isArray(data.hazard_ranking) ? data.hazard_ranking : []).map((value) => {
    const item = value as Record<string, unknown>;
    return {
      key: String(item.key ?? ""),
      label: String(item.label ?? "隐患"),
      count: Number(item.count ?? 0),
    } satisfies RankingItem;
  });

  const metrics = [
    { label: "待处理", value: Number(workflow.pending ?? 0), view: "open" },
    { label: "处理中", value: Number(workflow.in_progress ?? 0), view: "in_progress" },
    { label: "已超期", value: Number(workflow.overdue ?? 0), view: "overdue" },
    { label: "已关闭", value: Number(workflow.closed ?? 0), view: "closed" },
  ];

  return (
    <div className="page page--analytics">
      <PageTitle title="统计分析" description="统计只服务处置决策：先看积压，再看主要隐患和最近七天变化。" />

      {error ? <ErrorState message={error} retry={load} /> : null}
      {loading ? <Skeleton rows={5} /> : null}

      {!loading && !error ? (
        <>
          <section className="metric-ledger" aria-label="处置积压">
            <header>
              <h2>处置积压</h2>
              <p>点击任一数据打开对应记录视图。</p>
            </header>
            <div>
              {metrics.map((metric) => (
                <button key={metric.label} onClick={() => navigate("incidents", { view: metric.view })}>
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <ArrowRight size={18} aria-hidden="true" />
                </button>
              ))}
            </div>
          </section>

          <div className="analysis-grid">
            <section className="hazard-ranking">
              <SectionHead title="主要隐患排行" detail={`图片检测共 ${Number(checks.total_checks ?? 0)} 次，数据来自已保存记录。`} />
              {ranking.length ? (
                <div className="ranking-list">
                  {ranking.map((item, index) => {
                    const maximum = Math.max(...ranking.map((entry) => entry.count), 1);
                    return (
                      <button
                        key={item.key}
                        onClick={() => navigate("incidents", { view: item.key === "no-helmet" ? "red" : "yellow" })}
                      >
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <strong>{item.label}</strong>
                        <div aria-hidden="true"><i style={{ width: `${(item.count / maximum) * 100}%` }} /></div>
                        <em>{item.count}</em>
                        <ArrowRight size={18} aria-hidden="true" />
                      </button>
                    );
                  })}
                </div>
              ) : (
                <EmptyState title="暂无隐患排行" detail="完成图片检测并保存记录后，这里会显示主要隐患类型。" />
              )}
            </section>

            <section className="trend-sheet">
              <SectionHead title="近七天检测趋势" detail="折线显示每日检测次数，竖线标出其中的违规记录。" />
              {daily.length ? <TrendChart points={daily} /> : (
                <EmptyState title="暂无趋势数据" detail="最近七天没有图片检测记录。" />
              )}
              <Button tone="quiet" onClick={() => navigate("incidents", { view: "all" })}>
                <ListMagnifyingGlass size={19} aria-hidden="true" />查看全部记录
              </Button>
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}

function TrendChart({ points }: { points: DailyPoint[] }) {
  const width = 640;
  const height = 230;
  const padX = 34;
  const padTop = 24;
  const padBottom = 42;
  const maxValue = Math.max(...points.map((point) => point.checks), 1);
  const usableWidth = width - padX * 2;
  const usableHeight = height - padTop - padBottom;
  const positions = useMemo(() => points.map((point, index) => ({
    ...point,
    x: padX + (points.length === 1 ? usableWidth / 2 : index * usableWidth / (points.length - 1)),
    y: padTop + usableHeight - (point.checks / maxValue) * usableHeight,
  })), [points, maxValue]);
  const polyline = positions.map((point) => `${point.x},${point.y}`).join(" ");

  return (
    <div className="trend-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="最近七天每日检测与违规趋势">
        <path d={`M ${padX} ${padTop + usableHeight} H ${width - padX}`} className="chart-axis" />
        {positions.map((point) => {
          const violationHeight = point.checks ? (point.violations / maxValue) * usableHeight : 0;
          return (
            <g key={point.date}>
              <line
                x1={point.x}
                y1={padTop + usableHeight}
                x2={point.x}
                y2={padTop + usableHeight - violationHeight}
                className="chart-violation"
              />
              <text x={point.x} y={height - 15} textAnchor="middle">{point.date.slice(5)}</text>
            </g>
          );
        })}
        <polyline points={polyline} className="chart-line" />
        {positions.map((point) => (
          <g key={`point-${point.date}`}>
            <circle cx={point.x} cy={point.y} r="5" className="chart-point" />
            <text x={point.x} y={point.y - 12} textAnchor="middle" className="chart-value">{point.checks}</text>
          </g>
        ))}
      </svg>
      <div className="chart-legend">
        <span><ChartLine size={17} aria-hidden="true" />每日检测</span>
        <span className="legend-risk">违规记录</span>
      </div>
    </div>
  );
}
