import { useState } from "react";
import { type Step, Stepper } from "./components/Stepper";
import { Button } from "./components/ui/Button";
import { GeneratingStatus } from "./features/generate/GeneratingStatus";
import { PreviewScreen } from "./features/preview/PreviewScreen";
import { GroupingReview } from "./features/review-grouping/GroupingReview";
import { useBrandWorkflow } from "./features/workflow/useBrandWorkflow";
import { YamlEditor } from "./features/write-data/YamlEditor";
import { sampleYaml } from "./lib/sampleYaml";

export function App() {
  const [yamlText, setYamlText] = useState("");
  const [step, setStep] = useState<Step>("write");
  const [notice, setNotice] = useState<string | null>(null);
  const workflow = useBrandWorkflow({
    onAnalyzed: () => setStep("review"),
    onGenerated: () => setStep("preview"),
    onNotice: setNotice,
  });
  const { session, grouping, generated, yamlErrors } = workflow;
  const analyzeMutation = workflow.analyze;
  const groupingMutation = workflow.changeGrouping;
  const generateMutation = workflow.generate;
  const generationError = generateMutation.error?.message ?? null;

  function handleAnalyze(): void {
    setNotice(null);
    analyzeMutation.mutate(yamlText);
  }

  function startGenerate(): void {
    setStep("preview");
    generateMutation.mutate();
  }

  function goBackToData(): void {
    setStep("write");
    analyzeMutation.reset();
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
                  analyzeMutation.reset();
                }}
                onSample={() => {
                  setYamlText(sampleYaml);
                  analyzeMutation.reset();
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
      {step === "review" && session && grouping && (
        <GroupingReview
          brandName={session.brand_name}
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
          suggestions={session.suggestions ?? []}
        />
      )}
      {generateMutation.isPending && (
        <GeneratingStatus activeTypes={workflow.expectedTypes} error={null} />
      )}
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
        session &&
        generated && (
          <PreviewScreen
            checks={generated.check_results}
            onError={showError}
            onFixData={goBackToData}
            sessionId={session.session_id}
            types={workflow.generatedTypes}
          />
        )}
    </div>
  );
}
