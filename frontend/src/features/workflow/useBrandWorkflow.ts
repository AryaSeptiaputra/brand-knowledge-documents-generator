import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type AnalyzeResponse,
  api,
  type DocumentType,
  documentTypes,
  type ErrorDetail,
  type GenerateResponse,
  type Grouping,
} from "../../api/client";

export const workflowKeys = {
  session: ["session"] as const,
  grouping: (sessionId: string) => ["grouping", sessionId] as const,
  documents: (sessionId: string) => ["documents", sessionId] as const,
};

export class YamlErrorsShown extends Error {
  constructor(
    message: string,
    readonly details: ErrorDetail[],
  ) {
    super(message);
  }
}

export type GroupingToggle = { section: string; type: DocumentType; selected: boolean };

// Server data lives only in the query cache; skipToken reads entries written by mutations.
function useCached<T>(queryKey: readonly unknown[]): T | undefined {
  return useQuery<T>({ queryKey, queryFn: skipToken, staleTime: Number.POSITIVE_INFINITY }).data;
}

export function useBrandWorkflow({
  onAnalyzed,
  onGenerated,
  onNotice,
}: {
  onAnalyzed: () => void;
  onGenerated: () => void;
  onNotice: (message: string | null) => void;
}) {
  const queryClient = useQueryClient();
  const session = useCached<AnalyzeResponse>(workflowKeys.session);
  const sessionId = session?.session_id ?? "";
  const grouping = useCached<Grouping>(workflowKeys.grouping(sessionId));
  const generated = useCached<GenerateResponse>(workflowKeys.documents(sessionId));

  const analyze = useMutation({
    mutationFn: async (yaml: string): Promise<AnalyzeResponse> => {
      const { data, error, response } = await api.POST("/api/analyze", { body: { yaml } });
      if (error) {
        const details = response.status === 422 && "errors" in error ? (error.errors ?? []) : [];
        if (details.length > 0) throw new YamlErrorsShown(getApiMessage(error), details);
        throw new Error(getApiMessage(error));
      }
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(workflowKeys.session, data);
      queryClient.setQueryData(workflowKeys.grouping(data.session_id), data.grouping);
      onNotice(null);
      onAnalyzed();
    },
    // Located YAML errors already appear in the editor banner, so they skip the global notice.
    onError: (error) => {
      if (!(error instanceof YamlErrorsShown)) onNotice(error.message);
    },
  });

  const changeGrouping = useMutation({
    mutationFn: async ({ section, type, selected }: GroupingToggle): Promise<Grouping> => {
      if (!session || !grouping) throw new Error("Analyze the data before changing its grouping.");
      const entry = grouping.entries.find((item) => item.section === section);
      if (!entry) throw new Error("This data section is no longer available.");
      const nextTypes = selected
        ? [...new Set([...entry.document_types, type])]
        : entry.document_types.filter((item) => item !== type);
      const { data, error, response } = await api.PATCH("/api/grouping", {
        body: { session_id: session.session_id, section, document_types: nextTypes },
      });
      if (error) {
        if (response.status === 404)
          throw new Error("Your session expired. Submit your data again.");
        throw new Error(getApiMessage(error));
      }
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(workflowKeys.grouping(sessionId), data);
      onNotice(null);
    },
    onError: (error) => onNotice(error.message),
  });

  const generate = useMutation({
    mutationFn: async (): Promise<GenerateResponse> => {
      if (!session) throw new Error("Analyze the data before generating documents.");
      const { data, error } = await api.POST("/api/documents", {
        body: { session_id: session.session_id },
      });
      if (error) throw new Error(getApiMessage(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(workflowKeys.documents(sessionId), data);
      onNotice(null);
      onGenerated();
    },
  });

  const yamlErrors = analyze.error instanceof YamlErrorsShown ? analyze.error.details : [];

  return {
    session,
    grouping,
    generated,
    // Expected types while generating; the preview uses the types the backend actually produced.
    expectedTypes: toTypes(grouping?.entries.flatMap((entry) => entry.document_types) ?? []),
    generatedTypes: toTypes(generated?.documents.map((item) => item.document_type) ?? []),
    yamlErrors,
    analyze,
    changeGrouping,
    generate,
  };
}

function toTypes(types: DocumentType[]): DocumentType[] {
  const selected = new Set(types);
  return documentTypes.filter((type) => selected.has(type));
}

function getApiMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "errors" in error) {
    const errors = (error as { errors?: { message: string }[] }).errors;
    if (errors?.length) return errors.map((item) => item.message).join(" ");
  }
  return "The request could not be completed. Check the server and try again.";
}
