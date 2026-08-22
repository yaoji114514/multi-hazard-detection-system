import { useEffect, useState } from "react";
import { AppShell } from "./components/AppShell";
import { readRoute, type RouteState } from "./router";
import type { AppContext } from "./types";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ImagePage } from "./pages/ImagePage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { LivePage } from "./pages/LivePage";
import { VideoPage } from "./pages/VideoPage";

const CONTEXT_KEY = "site-safety-dispatch-context";

function initialContext(): AppContext {
  try {
    const saved = JSON.parse(localStorage.getItem(CONTEXT_KEY) ?? "{}");
    return {
      projectName: String(saved.projectName ?? ""),
      inspector: String(saved.inspector ?? ""),
    };
  } catch {
    return { projectName: "", inspector: "" };
  }
}

export function App() {
  const [route, setRoute] = useState<RouteState>(readRoute);
  const [context, setContext] = useState<AppContext>(initialContext);

  useEffect(() => {
    const syncRoute = () => setRoute(readRoute());
    window.addEventListener("hashchange", syncRoute);
    return () => window.removeEventListener("hashchange", syncRoute);
  }, []);

  useEffect(() => {
    localStorage.setItem(CONTEXT_KEY, JSON.stringify(context));
  }, [context]);

  let content;
  if (route.id === "live") content = <LivePage context={context} />;
  else if (route.id === "video") content = <VideoPage context={context} />;
  else if (route.id === "incidents") content = <IncidentsPage context={context} params={route.params} />;
  else if (route.id === "analytics") content = <AnalyticsPage />;
  else content = <ImagePage context={context} />;

  return (
    <AppShell route={route.id} context={context} onContextChange={setContext}>
      {content}
    </AppShell>
  );
}
