import createClient from "openapi-fetch";
import type { components, paths } from "./generated/schema";

export const api = createClient<paths>({ baseUrl: "" });

export type DocumentType = components["schemas"]["DocumentType"];
export type Grouping = components["schemas"]["Grouping"];
export type GroupingEntry = components["schemas"]["GroupingEntry"];
export type AnalyzeResponse = components["schemas"]["AnalyzeResponse"];
export type GenerateResponse = components["schemas"]["GenerateResponse"];
export type CheckResult = components["schemas"]["CheckResult"];
export type CompletenessSuggestion = components["schemas"]["CompletenessSuggestion"];
export type ErrorDetail = components["schemas"]["ErrorDetail"];
export type Document = components["schemas"]["Document"];

export const documentTypes: DocumentType[] = ["POLICY", "GUIDE", "PRODUCT_KNOWLEDGE"];

export const documentLabels: Record<DocumentType, string> = {
  POLICY: "Policy",
  GUIDE: "Guide",
  PRODUCT_KNOWLEDGE: "Product Knowledge",
};

export async function fetchPreview(sessionId: string, type: DocumentType): Promise<string> {
  const response = await fetch(
    `/api/documents/${type.toLowerCase()}/preview?session_id=${encodeURIComponent(sessionId)}`,
  );
  if (!response.ok) throw await responseError(response);
  return response.text();
}

export async function downloadDocument(
  sessionId: string,
  type: DocumentType | "all",
): Promise<void> {
  const response = await fetch(
    `/api/documents/${type.toLowerCase()}/pdf?session_id=${encodeURIComponent(sessionId)}`,
  );
  if (!response.ok) throw await responseError(response);
  const blob = await response.blob();
  const filename =
    response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/i)?.[1] ??
    (type === "all" ? "brand-documents.zip" : `${type.toLowerCase()}.pdf`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function uploadLogo(sessionId: string, file: File): Promise<void> {
  const form = new FormData();
  form.append("logo", file);
  const response = await fetch(`/api/logo?session_id=${encodeURIComponent(sessionId)}`, {
    method: "PUT",
    body: form,
  });
  if (!response.ok) throw await responseError(response);
}

export async function removeLogo(sessionId: string): Promise<void> {
  const response = await fetch(`/api/logo?session_id=${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
  if (!response.ok) throw await responseError(response);
}

async function responseError(response: Response): Promise<Error> {
  let message = `Request failed (${response.status}).`;
  try {
    const body = (await response.json()) as { errors?: ErrorDetail[] };
    if (body.errors?.length) message = body.errors.map((error) => error.message).join(" ");
  } catch {
    // Keep the status message when the server response is not JSON.
  }
  if (response.status === 404)
    message = `${message} Your session may have expired. Go back and submit the data again.`;
  return new Error(message);
}
