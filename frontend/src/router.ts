import type { RouteId } from "./types";

const routes: RouteId[] = ["image", "live", "video", "incidents", "analytics"];

export interface RouteState {
  id: RouteId;
  params: URLSearchParams;
}

export function readRoute(): RouteState {
  const value = window.location.hash.replace(/^#\/?/, "");
  const [rawId, rawQuery = ""] = value.split("?");
  const id = routes.includes(rawId as RouteId) ? (rawId as RouteId) : "image";
  return { id, params: new URLSearchParams(rawQuery) };
}

export function navigate(id: RouteId, params?: Record<string, string | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value) query.set(key, value);
  });
  const suffix = query.size ? `?${query.toString()}` : "";
  const next = `#/${id}${suffix}`;
  if (window.location.hash === next) {
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  } else {
    window.location.hash = next;
  }
}
