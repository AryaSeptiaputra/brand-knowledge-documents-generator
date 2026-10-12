import createClient from "openapi-fetch";
import type { components, paths } from "./generated/schema";

export const api = createClient<paths>({
  // An absolute same-origin base keeps Request() valid outside the browser, such as in tests.
  baseUrl: globalThis.location?.origin ?? "",
  // Resolve fetch per call so the current global (including test stubs) is used.
  fetch: (request) => globalThis.fetch(request),
});

export type DocumentType = components["schemas"]["DocumentType"];
export type Grouping = components["schemas"]["Grouping"];
export type GroupingEntry = components["schemas"]["GroupingEntry"];
export type AnalyzeResponse = components["schemas"]["AnalyzeResponse"];
export type GenerateResponse = components["schemas"]["GenerateResponse"];
export type CheckResult = components["schemas"]["CheckResult"];
export type CompletenessSuggestion = components["schemas"]["CompletenessSuggestion"];
export type ErrorDetail = components["schemas"]["ErrorDetail"];
export type Document = components["schemas"]["Document"];
export type LogoInfo = components["schemas"]["LogoInfo"];

const REVOKE_DELAY_MS = 1000;

export const documentTypes: DocumentType[] = ["POLICY", "GUIDE", "PRODUCT_KNOWLEDGE"];

export const documentLabels: Record<DocumentType, string> = {
  POLICY: "Policy",
  GUIDE: "Guide",
  PRODUCT_KNOWLEDGE: "Product Knowledge",
};

export async function fetchPreview(sessionId: string, type: DocumentType): Promise<string> {
  const { data, error, response } = await api.GET("/api/documents/{doc_type}/preview", {
    params: { path: { doc_type: type.toLowerCase() }, query: { session_id: sessionId } },
    parseAs: "text",
  });
  if (error !== undefined || data === undefined) throw toApiError(response, error);
  return data;
}

export async function downloadDocument(
  sessionId: string,
  type: DocumentType | "all",
): Promise<void> {
  const { data, error, response } = await api.GET("/api/documents/{doc_type}/pdf", {
    params: { path: { doc_type: type.toLowerCase() }, query: { session_id: sessionId } },
    parseAs: "blob",
  });
  if (error !== undefined || data === undefined) throw toApiError(response, error);
  const filename =
    // Reads the name from a header such as: attachment; filename="guide.pdf"
    response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/i)?.[1] ??
    (type === "all" ? "brand-documents.zip" : `${type.toLowerCase()}.pdf`);
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  // Some browsers start the download after click() returns, so the URL stays valid briefly.
  window.setTimeout(() => URL.revokeObjectURL(url), REVOKE_DELAY_MS);
}

export async function uploadLogo(sessionId: string, file: File): Promise<LogoInfo> {
  const { data, error, response } = await api.PUT("/api/logo", {
    params: { query: { session_id: sessionId } },
    // The generated type describes the binary part as a string; the browser sends the File.
    body: { logo: file as unknown as string },
    bodySerializer: (body) => {
      const form = new FormData();
      form.append("logo", body.logo);
      return form;
    },
  });
  if (error !== undefined || data === undefined) throw toApiError(response, error);
  return data;
}

export async function removeLogo(sessionId: string): Promise<void> {
  const { error, response } = await api.DELETE("/api/logo", {
    params: { query: { session_id: sessionId } },
  });
  if (!response.ok) throw toApiError(response, error);
}

function toApiError(response: Response, error: unknown): Error {
  let message = `Request failed (${response.status}).`;
  const errors = (error as { errors?: ErrorDetail[] } | undefined)?.errors;
  if (typeof error === "object" && errors?.length)
    message = errors.map((item) => item.message).join(" ");
  if (response.status === 404)
    message = `${message} Your session may have expired. Go back and submit the data again.`;
  return new Error(message);
}
