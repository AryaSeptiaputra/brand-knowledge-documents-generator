import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  type AnalyzeResponse,
  api,
  type CheckResult,
  type DocumentType,
  documentTypes,
  type ErrorDetail,
  type GenerateResponse,
  type Grouping,
} from "./api/client";
import { type Step, Stepper } from "./components/Stepper";
import { Button } from "./components/ui/Button";
import { GeneratingStatus } from "./features/generate/GeneratingStatus";
import { PreviewScreen } from "./features/preview/PreviewScreen";
import { GroupingReview } from "./features/review-grouping/GroupingReview";
import { YamlEditor } from "./features/write-data/YamlEditor";
import { sampleYaml } from "./lib/sampleYaml";

type WorkflowData = AnalyzeResponse & { checks?: CheckResult[] };

export function App() {
  const [yamlText, setYamlText] = useState("");
  const [step, setStep] = useState<Step>("write");
  const [workflow, setWorkflow] = useState<WorkflowData | null>(null);
  const [grouping, setGrouping] = useState<Grouping | null>(null);
  const [yamlErrors, setYamlErrors] = useState<ErrorDetail[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);

  const analyzeMutation = useMutation({
    mutationFn: async (): Promise<AnalyzeResponse> => {
      const { data, error, response } = await api.POST("/api/analyze", {
        body: { yaml: yamlText },
      });
      if (error) {
        if (response.status === 422 && "errors" in error) setYamlErrors(error.errors ?? []);
        throw new Error(getApiMessage(error));
      }
      return data;
    },
    onSuccess: (data) => {
      setWorkflow(data);
      setGrouping(data.grouping);
      setYamlErrors([]);
      setNotice(null);
      setStep("review");
    },
    onError: (error) => setNotice(error.message),
  });

  const groupingMutation = useMutation({
    mutationFn: async ({
      section,
      type,
      selected,
    }: {
      section: string;
      type: DocumentType;
      selected: boolean;
    }) => {
      if (!workflow || !grouping) throw new Error("Analyze the data before changing its grouping.");
      const entry = grouping.entries.find((item) => item.section === section);
      if (!entry) throw new Error("This data section is no longer available.");
      const nextTypes = selected
        ? [...new Set([...entry.document_types, type])]
        : entry.document_types.filter((item) => item !== type);
      const { data, error, response } = await api.PATCH("/api/grouping", {
        body: { session_id: workflow.session_id, section, document_types: nextTypes },
      });
      if (error) throw new Error(getApiMessage(error));
      if (response.status === 404) throw new Error("Your session expired. Submit your data again.");
      return data;
    },
    onSuccess: (data) => {
      setGrouping(data);
      setNotice(null);
    },
    onError: (error) => setNotice(error.message),
  });

  const generateMutation = useMutation({
    mutationFn: async (): Promise<GenerateResponse> => {
      if (!workflow) throw new Error("Analyze the data before generating documents.");
      const { data, error } = await api.POST("/api/documents", {
        body: { session_id: workflow.session_id },
      });
      if (error) throw new Error(getApiMessage(error));
      return data;
    },
    onSuccess: (data) => {
      setWorkflow((previous) =>
        previous ? { ...previous, checks: data.check_results } : previous,
      );
      setGenerationError(null);
      setNotice(null);
      setStep("preview");
    },
    onError: (error) => setGenerationError(error.message),
  });

  const activeTypes = useMemo(() => {
    const selected = new Set(grouping?.entries.flatMap((entry) => entry.document_types) ?? []);
    return documentTypes.filter((type) => selected.has(type));
  }, [grouping]);

  function handleAnalyze(): void {
    setNotice(null);
    setYamlErrors([]);
    analyzeMutation.mutate();
  }

  function startGenerate(): void {
    setStep("preview");
    setGenerationError(null);
    generateMutation.mutate();
  }

  function goBackToData(): void {
    setStep("write");
    setYamlErrors([]);
    setNotice(null);
  }

  function showError(message: string): void {
    setNotice(message);
  }

  const analyzing = analyzeMutation.isPending;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <span aria-hidden="true" className="app-mark" />
          <span>Brand Knowledge Document Generator</span>
        </div>
        <Stepper active={step} />
      </header>
      {notice && (
        <div className="global-notice" role="alert">
          <span>{notice}</span>
          <button aria-label="Dismiss message" onClick={() => setNotice(null)} type="button">
            ×
          </button>
        </div>
      )}
      {step === "write" && (
        <main className="main-content">
          <div className="page-heading">
            <h1>Write your brand data</h1>
            <p>
              Free-form YAML. Only <code>brand</code> is required.
            </p>
          </div>
          {yamlErrors.length > 0 && (
            <div className="error-banner" role="alert">
              <strong>We couldn't read this YAML.</strong>
              <span>Fix the highlighted lines and try again.</span>
            </div>
          )}
          <div className="content-columns editor-layout">
            <div className="editor-column">
              <YamlEditor
                errors={yamlErrors}
                onChange={setYamlText}
                onClear={() => {
                  setYamlText("");
                  setYamlErrors([]);
                }}
                onSample={() => {
                  setYamlText(sampleYaml);
                  setYamlErrors([]);
                  setNotice(null);
                }}
                value={yamlText}
              />
              <div className="editor-footer">
                <span>{yamlText.split("\n").length} lines</span>
                <Button
                  disabled={analyzing || !yamlText.trim()}
                  onClick={handleAnalyze}
                  variant="primary"
                >
                  {analyzing ? "Checking data…" : "Check data and continue"}
                </Button>
              </div>
            </div>
            <aside className="writing-aside">
              <section className="card">
                <h2>Two kinds of data</h2>
                <div className="kind-explanation">
                  <span className="chip">General brand knowledge</span>
                  <p>Returns, shipping, payment, warranty</p>
                </div>
                <div className="kind-explanation">
                  <span className="chip">Product knowledge</span>
                  <p>Size, material, variants per product</p>
                </div>
              </section>
              <section className="card">
                <h2>Writing tips</h2>
                <ul className="simple-list">
                  <li>
                    Start with <code>brand: Your Brand</code>
                  </li>
                  <li>Use spaces for indentation, not tabs</li>
                  <li>Keep facts under clear section names</li>
                </ul>
              </section>
              <section className="card">
                <h2>You will get</h2>
                <p>
                  Customer-ready documents as searchable PDFs, with every fact checked against your
                  data.
                </p>
              </section>
            </aside>
          </div>
        </main>
      )}
      {step === "review" && workflow && grouping && (
        <GroupingReview
          brandName={workflow.brand_name}
          busy={groupingMutation.isPending}
          sectionCount={grouping.entries.length}
          grouping={grouping}
          onBack={goBackToData}
          onGenerate={startGenerate}
          onToggle={(section, type, selected) => {
            setNotice(null);
            groupingMutation.mutate({ section, type, selected });
          }}
          productCount={
            new Set(
              grouping.entries
                .filter((item) => item.unit_kind !== "GENERAL_SECTION")
                .map((item) => item.section.split(".").slice(0, 2).join(".")),
            ).size
          }
          suggestions={workflow.suggestions ?? []}
        />
      )}
      {generateMutation.isPending && <GeneratingStatus activeTypes={activeTypes} error={null} />}
      {step === "preview" && !generateMutation.isPending && generationError && (
        <main className="generating-page">
          <section className="generating-card">
            <div>
              <h1>Generation failed</h1>
              <p role="alert">{generationError}</p>
            </div>
            <div className="page-actions">
              <Button onClick={() => setStep("review")}>Back to grouping</Button>
              <Button onClick={startGenerate} variant="primary">
                Try again
              </Button>
            </div>
          </section>
        </main>
      )}
      {step === "preview" &&
        !generateMutation.isPending &&
        !generationError &&
        workflow?.checks && (
          <PreviewScreen
            checks={workflow.checks}
            onError={showError}
            onFixData={goBackToData}
            sessionId={workflow.session_id}
            types={activeTypes}
          />
        )}
    </div>
  );
}

function getApiMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "errors" in error) {
    const errors = (error as { errors?: { message: string }[] }).errors;
    if (errors?.length) return errors.map((item) => item.message).join(" ");
  }
  return "The request could not be completed. Check the server and try again.";
}
