import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Camera,
  CheckCircle,
  DownloadSimple,
  Record,
  Stop,
  WarningCircle,
} from "@phosphor-icons/react";
import { deleteRealtimeSession, detectRealtimeFrame, normalizeDetections, normalizeRisk } from "../api";
import { navigate } from "../router";
import type { AppContext, Detection, RiskLevel } from "../types";
import { Button, DetectionOverlay, PageTitle, RiskMark } from "../components/Common";

type MonitorState = "idle" | "requesting" | "running" | "stopped";

function makeSessionId() {
  return `web-${crypto.randomUUID().replaceAll("-", "").slice(0, 24)}`;
}

export function LivePage({ context }: { context: AppContext }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const inFlightRef = useRef(false);
  const timerRef = useRef<number | undefined>(undefined);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const sessionRef = useRef(makeSessionId());

  const [monitor, setMonitor] = useState<MonitorState>("idle");
  const [systemError, setSystemError] = useState("");
  const [risk, setRisk] = useState<RiskLevel>("unknown");
  const [detections, setDetections] = useState<Detection[]>([]);
  const [violations, setViolations] = useState(0);
  const [stored, setStored] = useState(0);
  const [latestRecord, setLatestRecord] = useState<{ id: string | number; source: string }>();
  const [notificationState, setNotificationState] = useState("等待风险事件");
  const [recording, setRecording] = useState(false);

  const clearTimer = () => {
    if (timerRef.current !== undefined) window.clearInterval(timerRef.current);
    timerRef.current = undefined;
  };

  const releaseMedia = () => {
    clearTimer();
    recorderRef.current?.state === "recording" && recorderRef.current.stop();
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setRecording(false);
  };

  useEffect(() => {
    return () => releaseMedia();
  }, []);

  const processFrame = async () => {
    if (inFlightRef.current || monitor !== "running") return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) return;
    inFlightRef.current = true;
    canvas.width = width;
    canvas.height = height;
    canvas.getContext("2d")?.drawImage(video, 0, 0, width, height);
    try {
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.82));
      if (!blob) throw new Error("无法提取摄像头画面。");
      const response = await detectRealtimeFrame(
        blob,
        sessionRef.current,
        context.projectName.trim(),
        context.inspector.trim(),
      );
      const nextDetections = normalizeDetections(response.detections);
      const session = ((response.session ?? {}) || {}) as Record<string, unknown>;
      const storedEvents = Array.isArray(response.stored_events) ? response.stored_events : [];
      setDetections(nextDetections);
      setRisk(normalizeRisk(response.risk));
      setViolations(Number(session.observed_violations ?? 0));
      setStored(Number(session.stored_count ?? 0));
      const latest = storedEvents.at(-1) as Record<string, unknown> | undefined;
      if (latest?.record_id !== undefined) {
        setLatestRecord({ id: latest.record_id as string | number, source: "realtime" });
      }
      const notification = ((response.notification ?? {}) || {}) as Record<string, unknown>;
      const status = String(session.notification_status ?? notification.status ?? "idle");
      setNotificationState(
        status === "failed"
          ? "通知发送失败"
          : status === "retrying"
            ? "通知等待重试"
            : status === "queued"
              ? "通知正在发送"
              : status === "sent"
                ? "通知已送达"
                 : "等待风险事件",
      );
      const lastError = String(session.last_error ?? "");
      const notificationError = String(session.notification_error ?? "");
      const retryAt = Number(session.retry_at ?? 0);
      const retrySeconds = retryAt > 0 ? Math.max(0, Math.ceil(retryAt - Date.now() / 1000)) : 0;
      const notificationProblem = status === "retrying"
        ? "正在自动重试风险通知，记录与证据已保留。"
        : status === "failed"
          ? notificationError || `通知发送失败${retrySeconds ? `，约 ${retrySeconds} 秒后自动重试` : ""}。`
          : "";
      setSystemError(lastError || notificationProblem);
    } catch (reason) {
      setSystemError(reason instanceof Error ? reason.message : "实时检测请求失败。");
    } finally {
      inFlightRef.current = false;
    }
  };

  const startCamera = async () => {
    if (!context.projectName.trim() || !context.inspector.trim()) {
      setSystemError("请先在顶部填写项目名称和检查人，再连接摄像头。");
      return;
    }
    setSystemError("");
    setMonitor("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "environment" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setMonitor("running");
      setRisk("unknown");
      clearTimer();
      timerRef.current = window.setInterval(() => void processFrame(), 1200);
    } catch (reason) {
      setMonitor("stopped");
      setSystemError(
        reason instanceof DOMException && reason.name === "NotAllowedError"
          ? "摄像头权限被拒绝，请在浏览器地址栏重新允许。"
          : "无法连接摄像头，请检查设备是否被其他程序占用。",
      );
    }
  };

  useEffect(() => {
    if (monitor !== "running") return;
    clearTimer();
    timerRef.current = window.setInterval(() => void processFrame(), 1200);
    return clearTimer;
  }, [monitor, context.projectName, context.inspector]);

  const stopCamera = async () => {
    releaseMedia();
    setMonitor("stopped");
  };

  const resetSession = async () => {
    releaseMedia();
    try {
      await deleteRealtimeSession(sessionRef.current);
    } catch (reason) {
      setSystemError(reason instanceof Error ? reason.message : "实时会话未能清理。");
      return;
    }
    sessionRef.current = makeSessionId();
    setMonitor("idle");
    setRisk("unknown");
    setDetections([]);
    setViolations(0);
    setStored(0);
    setLatestRecord(undefined);
    setNotificationState("等待风险事件");
    setSystemError("");
  };

  const toggleRecording = () => {
    const stream = streamRef.current;
    if (!stream) return;
    if (typeof MediaRecorder === "undefined") {
      setSystemError("当前浏览器不支持本机视频录制。");
      return;
    }
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    chunksRef.current = [];
    const recorder = MediaRecorder.isTypeSupported("video/webm")
      ? new MediaRecorder(stream, { mimeType: "video/webm" })
      : new MediaRecorder(stream);
    recorder.ondataavailable = (event) => {
      if (event.data.size) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "video/webm" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `现场录制_${new Date().toISOString().replaceAll(":", "-")}.webm`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    recorder.start(1000);
    recorderRef.current = recorder;
    setRecording(true);
  };

  const monitorLabel = {
    idle: "摄像头未连接",
    requesting: "正在申请摄像头权限",
    running: "监测正在运行",
    stopped: "监测已停止",
  }[monitor];

  return (
    <div className="page page--live">
      <PageTitle title="实时检测" description="现场画面留在主舞台，监测状态、业务风险和系统错误分别呈现。" />

      <div className="live-layout">
        <section className="live-stage">
          <header className="bench-head">
            <div>
              <span>摄像头现场</span>
              <strong>{monitorLabel}</strong>
            </div>
            <div className="live-status">
              {monitor === "running" ? <CheckCircle size={18} weight="fill" aria-hidden="true" /> : <Camera size={18} aria-hidden="true" />}
              {monitorLabel}
            </div>
          </header>
          <div className="camera-frame">
            <img className={monitor === "running" ? "is-hidden" : ""} src={SAMPLE_URL} alt="摄像头连接前的现场示例" />
            <video ref={videoRef} muted playsInline className={monitor === "running" ? "" : "is-hidden"} />
            {monitor === "running" ? (
              <DetectionOverlay
                detections={detections}
                sourceWidth={videoRef.current?.videoWidth}
                sourceHeight={videoRef.current?.videoHeight}
              />
            ) : null}
            {monitor === "requesting" ? <div className="camera-request">正在等待浏览器授权</div> : null}
            {recording ? (
              <div className="recording-flag"><Record size={16} weight="fill" aria-hidden="true" />本机录制中</div>
            ) : null}
          </div>
          <div className="camera-controls">
            {monitor !== "running" ? (
              <Button tone="primary" onClick={startCamera} busy={monitor === "requesting"}>
                <Camera size={20} aria-hidden="true" />连接摄像头
              </Button>
            ) : (
              <Button tone="danger" onClick={stopCamera}>
                <Stop size={20} weight="fill" aria-hidden="true" />停止监测
              </Button>
            )}
            <Button tone="neutral" onClick={toggleRecording} disabled={monitor !== "running"}>
              {recording ? <DownloadSimple size={20} aria-hidden="true" /> : <Record size={20} aria-hidden="true" />}
              {recording ? "停止并下载" : "本机录制"}
            </Button>
            <button className="text-button" onClick={resetSession}>重置本次会话</button>
          </div>
          <canvas ref={canvasRef} hidden />
        </section>

        <aside className="live-command">
          <header>
            <div>
              <h2>现场签派</h2>
              <p>{context.projectName || "请先填写项目"}</p>
            </div>
          </header>

          <div className="live-metrics">
            <div>
              <span>累计违规</span>
              <strong>{violations}</strong>
            </div>
            <div>
              <span>已存记录</span>
              <strong>{stored}</strong>
            </div>
          </div>

          <div className="state-stack">
            <section>
              <span>监测状态</span>
              <strong>{monitorLabel}</strong>
              <p>{monitor === "running" ? "浏览器单帧在途，上一帧完成后才发送下一帧。" : "未运行时不会调用实时检测接口。"}</p>
            </section>
            <section>
              <span>当前业务风险</span>
              <RiskMark risk={risk} />
              <p>{risk === "red" ? "发现需立即处理的安全帽风险。" : risk === "yellow" ? "发现需限时整改的穿戴风险。" : risk === "safe" ? "当前画面未发现需处置风险。" : "等待首个检测结果。"}</p>
            </section>
            <section className={systemError ? "has-error" : ""}>
              <span>系统状态</span>
              <strong>{systemError ? "需要处理" : "检测链路正常"}</strong>
              <p>{systemError || notificationState}</p>
            </section>
          </div>

          {latestRecord ? (
            <Button tone="neutral" onClick={() => navigate("incidents", { focus: `${latestRecord.source}:${latestRecord.id}` })}>
              查看最新处置记录
              <ArrowRight size={18} aria-hidden="true" />
            </Button>
          ) : null}
          {systemError ? (
            <div className="inline-warning" role="alert">
              <WarningCircle size={18} weight="fill" aria-hidden="true" />
              {systemError.includes("通知")
                ? "系统会自动重试通知；检测记录与证据不受影响。"
                : "错误会持续显示，直到重置或重新连接。"}
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

const SAMPLE_URL = "/api/sample";
