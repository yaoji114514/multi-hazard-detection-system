import { useEffect, useRef, useState } from "react";
import { Check, DownloadSimple, FilmStrip, UploadSimple, WarningCircle } from "@phosphor-icons/react";
import { createVideoJob, getVideoJob, mediaUrl } from "../api";
import type { AppContext } from "../types";
import { Button, ErrorState, PageTitle } from "../components/Common";

type JobState = "idle" | "uploading" | "queued" | "processing" | "completed" | "failed";

export function VideoPage({ context }: { context: AppContext }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState<JobState>("idle");
  const [progress, setProgress] = useState(0);
  const [summary, setSummary] = useState<Record<string, unknown>>({});
  const [resultUrl, setResultUrl] = useState("");
  const [error, setError] = useState("");
  const pollRef = useRef<number | undefined>(undefined);

  const stopPolling = () => {
    if (pollRef.current !== undefined) window.clearTimeout(pollRef.current);
    pollRef.current = undefined;
  };

  useEffect(() => {
    return () => {
      stopPolling();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const chooseFile = (next: File | null) => {
    if (!next) return;
    stopPolling();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(next);
    setPreviewUrl(URL.createObjectURL(next));
    setJobId("");
    setStatus("idle");
    setProgress(0);
    setSummary({});
    setResultUrl("");
    setError("");
  };

  const poll = async (id: string) => {
    try {
      const job = await getVideoJob(id);
      const nextStatus = String(job.status ?? "processing") as JobState;
      setStatus(nextStatus);
      setProgress(Math.max(0, Math.min(1, Number(job.progress ?? 0))));
      setSummary(((job.summary ?? {}) || {}) as Record<string, unknown>);
      setResultUrl(mediaUrl(job.result_url) ?? "");
      if (nextStatus === "completed") return;
      if (nextStatus === "failed") {
        setError(String(job.error ?? "视频处理失败，请重新提交。"));
        return;
      }
      pollRef.current = window.setTimeout(() => void poll(id), 1200);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法获取视频任务进度。");
      pollRef.current = window.setTimeout(() => void poll(id), 2500);
    }
  };

  const start = async () => {
    if (!file) {
      setError("请先选择需要处理的视频文件。");
      return;
    }
    stopPolling();
    setStatus("uploading");
    setError("");
    try {
      const job = await createVideoJob(file, context.projectName, context.inspector);
      const id = String(job.job_id ?? job.id ?? "");
      if (!id) throw new Error("服务未返回视频任务编号。");
      setJobId(id);
      setStatus(String(job.status ?? "queued") as JobState);
      setProgress(Number(job.progress ?? 0));
      void poll(id);
    } catch (reason) {
      setStatus("failed");
      setError(reason instanceof Error ? reason.message : "视频任务创建失败。");
    }
  };

  const statusLabel: Record<JobState, string> = {
    idle: "等待开始",
    uploading: "正在上传",
    queued: "等待处理",
    processing: "正在逐帧检测",
    completed: "处理完成",
    failed: "处理失败",
  };

  const percent = Math.round(progress * 100);

  return (
    <div className="page page--video">
      <PageTitle title="视频检测" description="上传一段现场视频，生成带标注的复核文件。此能力不进入隐患处置队列。" />

      <section className="boundary-notice">
        <WarningCircle size={24} weight="fill" aria-hidden="true" />
        <div>
          <strong>开始前请确认能力边界</strong>
          <p>视频检测不建记录、不入处置队列、不发送钉钉。统计按视频帧累计，同一人员可能被重复计数。</p>
        </div>
      </section>

      <div className="video-layout">
        <section className="video-stage">
          <header className="bench-head">
            <div>
              <span>待处理视频</span>
              <strong>{file?.name ?? "尚未选择文件"}</strong>
            </div>
            <label className="button button--neutral file-button">
              <UploadSimple size={18} aria-hidden="true" />
              选择视频
              <input
                type="file"
                accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm"
                onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
              />
            </label>
          </header>
          <div className="video-frame">
            {resultUrl ? (
              <video src={resultUrl} controls playsInline aria-label="已完成的标注视频" />
            ) : previewUrl ? (
              <video src={previewUrl} controls playsInline aria-label={`待处理视频 ${file?.name ?? ""}`} />
            ) : (
              <div className="video-empty">
                <FilmStrip size={46} weight="thin" aria-hidden="true" />
                <strong>把现场视频放上校样台</strong>
                <span>支持 MP4、MOV、AVI、MKV 和 WebM，单个文件上限由本地服务决定。</span>
              </div>
            )}
          </div>
          {resultUrl ? (
            <a className="button button--neutral" href={resultUrl} download>
              <DownloadSimple size={19} aria-hidden="true" />下载标注视频
            </a>
          ) : null}
        </section>

        <aside className="video-command">
          <header>
            <h2>处理命令</h2>
            <p>上传后仍需明确开始，不会自动消耗推理资源。</p>
          </header>
          <dl className="dispatch-facts">
            <div><dt>输入</dt><dd>{file?.name ?? "尚未选择"}</dd></div>
            <div><dt>输出</dt><dd>H.264 标注视频</dd></div>
            <div><dt>处置记录</dt><dd>不会创建</dd></div>
            <div><dt>钉钉通知</dt><dd>不会发送</dd></div>
          </dl>
          <Button
            tone="primary"
            busy={status === "uploading"}
            disabled={!file || status === "queued" || status === "processing"}
            onClick={start}
          >
            开始视频检测
          </Button>

          {status !== "idle" ? (
            <div className="job-progress" role="status" aria-live="polite">
              <div>
                <strong>{statusLabel[status]}</strong>
                <span>{status === "completed" ? "完成" : `${percent}%`}</span>
              </div>
              <div className="progress-line" aria-hidden="true"><span style={{ width: `${percent}%` }} /></div>
              {jobId ? <small>任务 {jobId.slice(0, 12)}</small> : null}
            </div>
          ) : null}

          {status === "completed" ? (
            <div className="video-summary">
              <Check size={20} weight="bold" aria-hidden="true" />
              <div><span>累计检测目标</span><strong>{Number(summary.total_detections ?? 0)}</strong></div>
              <div><span>红色帧目标</span><strong>{Number(summary.red_alerts ?? 0)}</strong></div>
              <div><span>黄色帧目标</span><strong>{Number(summary.yellow_alerts ?? 0)}</strong></div>
            </div>
          ) : null}
        </aside>
      </div>

      {error ? <ErrorState message={error} retry={jobId ? () => void poll(jobId) : start} /> : null}
    </div>
  );
}
