import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Check,
  ImageSquare,
  UploadSimple,
  WarningCircle,
} from "@phosphor-icons/react";
import { detectImage } from "../api";
import { navigate } from "../router";
import type { AppContext, ImageDetectionResult } from "../types";
import {
  Button,
  DetectionOverlay,
  ErrorState,
  PageTitle,
  RiskMark,
  confidenceText,
} from "../components/Common";

const SAMPLE_URL = "/api/sample";

export function ImagePage({ context }: { context: AppContext }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState(SAMPLE_URL);
  const [useSample, setUseSample] = useState(true);
  const [result, setResult] = useState<ImageDetectionResult | null>(null);
  const [view, setView] = useState<"original" | "annotated">("original");
  const [selectedDetection, setSelectedDetection] = useState<string>();
  const [imageSize, setImageSize] = useState<{ width: number; height: number }>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    return () => {
      if (previewUrl.startsWith("blob:")) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const contextReady = Boolean(context.projectName.trim() && context.inspector.trim());
  const activeImage = view === "annotated" && result?.annotatedUrl
    ? result.annotatedUrl
    : result?.originalUrl ?? previewUrl;
  const selected = useMemo(
    () => result?.detections.find((item) => item.id === selectedDetection),
    [result, selectedDetection],
  );

  const chooseFile = (next: File | null) => {
    if (!next) return;
    if (previewUrl.startsWith("blob:")) URL.revokeObjectURL(previewUrl);
    setFile(next);
    setPreviewUrl(URL.createObjectURL(next));
    setUseSample(false);
    setResult(null);
    setSelectedDetection(undefined);
    setView("original");
    setError("");
  };

  const chooseSample = () => {
    if (previewUrl.startsWith("blob:")) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl(SAMPLE_URL);
    setUseSample(true);
    setResult(null);
    setSelectedDetection(undefined);
    setView("original");
    setError("");
  };

  const startDetection = async () => {
    if (!contextReady) {
      setError("请先在顶部填写项目名称和检查人，再开始检测。");
      return;
    }
    setLoading(true);
    setError("");
    try {
      let source = file;
      if (!source && useSample) {
        const response = await fetch(SAMPLE_URL);
        if (!response.ok) throw new Error("内置示例图片暂不可用。");
        source = new File([await response.blob()], "sample.jpg", { type: "image/jpeg" });
      }
      if (!source) throw new Error("请先上传现场图片。");
      const next = await detectImage(source, context.projectName.trim(), context.inspector.trim());
      setResult(next);
      setView(next.annotatedUrl ? "annotated" : "original");
      setSelectedDetection(next.detections[0]?.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "图片检测失败，请重试。");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page page--image">
      <PageTitle
        title="隐患检测"
        description="把现场照片放上校样台，先核对证据，再发起一次明确检测。"
      />

      <div className="proofing-layout">
        <section className="evidence-bench" aria-label="现场证据校样台">
          <header className="bench-head">
            <div>
              <span>现场证据</span>
              <strong>{file?.name ?? "内置示例"}</strong>
            </div>
            <div className="bench-tools">
              {result?.annotatedUrl ? (
                <div className="segmented" aria-label="图像视图">
                  <button className={view === "original" ? "is-active" : ""} onClick={() => setView("original")}>原图</button>
                  <button className={view === "annotated" ? "is-active" : ""} onClick={() => setView("annotated")}>AI 标注</button>
                </div>
              ) : null}
              <label className="button button--neutral file-button">
                <UploadSimple size={18} aria-hidden="true" />
                上传图片
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/bmp"
                  onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
                />
              </label>
            </div>
          </header>

          <div className={`evidence-frame ${loading ? "is-processing" : ""}`}>
            <img
              src={activeImage}
              alt={file ? `待检测现场图片 ${file.name}` : "内置施工现场检测示例"}
              onLoad={(event) => setImageSize({
                width: event.currentTarget.naturalWidth,
                height: event.currentTarget.naturalHeight,
              })}
            />
            {view === "original" && result ? (
              <DetectionOverlay
                detections={result.detections}
                selectedId={selectedDetection}
                sourceWidth={result.width ?? imageSize?.width}
                sourceHeight={result.height ?? imageSize?.height}
              />
            ) : null}
            {loading ? (
              <div className="processing-plate" role="status">
                <span />
                <strong>正在校验现场影像</strong>
                <small>本次结果完成后才会生成记录与通知</small>
              </div>
            ) : null}
          </div>

          <div className="bench-foot">
            <button className="text-button" onClick={chooseSample} disabled={useSample && !file}>
              <ImageSquare size={18} aria-hidden="true" />
              使用内置示例
            </button>
            <span>{result ? `${result.detections.length} 个检测目标` : "图片检测不会在刷新页面时自动运行"}</span>
          </div>
        </section>

        <aside className="dispatch-strip" aria-label="检测签派条">
          <header>
            <div>
              <h2>检测命令</h2>
              <p>确认上下文和证据后再执行</p>
            </div>
          </header>

          <dl className="dispatch-facts">
            <div>
              <dt>项目</dt>
              <dd>{context.projectName || "尚未填写"}</dd>
            </div>
            <div>
              <dt>检查人</dt>
              <dd>{context.inspector || "尚未填写"}</dd>
            </div>
            <div>
              <dt>证据</dt>
              <dd>{file?.name ?? (useSample ? "内置示例" : "尚未选择")}</dd>
            </div>
          </dl>

          <div className="readiness-list" aria-label="检测准备状态">
            <span className={contextReady ? "is-ready" : ""}>
              {contextReady ? <Check size={17} weight="bold" aria-hidden="true" /> : <WarningCircle size={17} aria-hidden="true" />}
              检查上下文
            </span>
            <span className={previewUrl ? "is-ready" : ""}>
              <Check size={17} weight="bold" aria-hidden="true" />
              现场图片
            </span>
            <span>
              <Check size={17} weight="bold" aria-hidden="true" />
              本地记录
            </span>
          </div>

          <Button
            tone="primary"
            className="dispatch-action"
            busy={loading}
            disabled={!contextReady || (!file && !useSample)}
            onClick={startDetection}
          >
            开始检测
            <ArrowRight size={22} weight="bold" aria-hidden="true" />
          </Button>
          <p className="dispatch-note">开始后将执行推理、保存记录，并按风险配置发送通知。</p>
        </aside>
      </div>

      {error ? <ErrorState message={error} retry={startDetection} /> : null}

      {result ? (
        <section className={`result-sheet result-sheet--${result.risk}`}>
          <header className="result-sheet__summary">
            <div>
              <RiskMark risk={result.risk} label={result.riskLabel} />
              <h2>{result.action}</h2>
              <p>
                {result.notification?.status === "sent"
                  ? `通知已发送至 ${result.notification.sentCount ?? 0} 个群。`
                  : result.notification?.status === "failed"
                    ? "记录已保存，但通知发送失败，请检查群配置。"
                    : "本次结果不需要发送风险通知。"}
              </p>
            </div>
            {result.id !== undefined ? (
              <Button
                tone="neutral"
                onClick={() => navigate("incidents", { focus: `${result.source ?? "image"}:${result.id}` })}
              >
                进入处置记录
                <ArrowRight size={18} aria-hidden="true" />
              </Button>
            ) : null}
          </header>

          <div className="contact-strip" aria-label="检测目标联系条">
            {result.detections.length ? result.detections.map((detection, index) => (
              <button
                key={detection.id}
                className={selectedDetection === detection.id ? "is-selected" : ""}
                onClick={() => {
                  setSelectedDetection(detection.id);
                  setView("original");
                }}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{detection.label}</strong>
                <RiskMark risk={detection.risk} />
                <small>{confidenceText(detection.confidence)}</small>
              </button>
            )) : (
              <p className="contact-strip__empty">模型没有返回可定位目标，请人工复核整张图片。</p>
            )}
          </div>
          {selected ? (
            <p className="selection-hint" role="status">
              已在原图定位：{selected.label} {confidenceText(selected.confidence)}
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
