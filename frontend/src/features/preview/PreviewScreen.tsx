import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  type CheckResult,
  type DocumentType,
  documentLabels,
  downloadDocument,
  fetchPreview,
} from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";
import { Tabs, TabsList, TabsTrigger } from "../../components/ui/Tabs";
import { useLogo } from "./useLogo";

export function PreviewScreen({
  sessionId,
  types,
  checks,
  onFixData,
  onError,
}: {
  sessionId: string;
  types: DocumentType[];
  checks: CheckResult[];
  onFixData: () => void;
  onError: (message: string) => void;
}) {
  const [selectedType, setSelectedType] = useState(types[0] ?? "POLICY");
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [showSources, setShowSources] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const previewQuery = useQuery({
    queryKey: ["preview", sessionId, selectedType],
    queryFn: () => fetchPreview(sessionId, selectedType),
    enabled: types.includes(selectedType),
  });
  const { logoName, upload: logoMutation, remove: removeMutation } = useLogo(sessionId, onError);
  const downloadMutation = useMutation({
    mutationFn: (type: DocumentType | "all") => downloadDocument(sessionId, type),
    onError: (error) => onError(error.message),
  });
  const check = checks.find((item) => item.document_type === selectedType);
  const replacedParagraphs = check?.replaced_paragraphs ?? [];
  const uncoveredFacts = check?.uncovered_facts ?? [];
  const errorMessage = previewQuery.error?.message;

  useEffect(() => {
    const firstType = types.at(0);
    if (firstType && !types.includes(selectedType)) setSelectedType(firstType);
  }, [selectedType, types]);

  if (types.length === 0) {
    return (
      <main className="main-content preview-main">
        <div className="error-banner" role="alert">
          No documents were generated. Make sure at least one data section is included in a
          document.
          <Button onClick={onFixData}>Fix data</Button>
        </div>
      </main>
    );
  }

  return (
    <main className="main-content preview-main">
      <div className="preview-toolbar">
        <Tabs
          onValueChange={(value) => setSelectedType(value as DocumentType)}
          value={selectedType}
        >
          <TabsList aria-label="Document type">
            {types.map((type) => (
              <TabsTrigger key={type} value={type}>
                {documentLabels[type]}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="preview-actions">
          <label className="source-toggle" htmlFor="show-source-references">
            <Checkbox
              checked={showSources}
              className="size-4.5"
              id="show-source-references"
              onCheckedChange={(checked) => setShowSources(checked === true)}
            />
            Show source references
          </label>
          <Button onClick={onFixData}>Fix data</Button>
          <Button
            disabled={downloadMutation.isPending}
            onClick={() => downloadMutation.mutate("all")}
          >
            {downloadMutation.isPending ? "Preparing…" : "Download all (ZIP)"}
          </Button>
          <Button
            disabled={downloadMutation.isPending}
            onClick={() => downloadMutation.mutate(selectedType)}
            variant="primary"
          >
            Download PDF
          </Button>
        </div>
      </div>
      <div className="content-columns preview-columns">
        <section aria-label="Document preview" className="preview-canvas">
          {previewQuery.isLoading && (
            <div className="preview-loading" role="status">
              Loading preview…
            </div>
          )}
          {errorMessage && (
            <div className="error-banner" role="alert">
              {errorMessage}
              <Button onClick={onFixData}>Fix data</Button>
            </div>
          )}
          {previewQuery.data && (
            <iframe
              className="document-frame"
              key={`${selectedType}-${previewQuery.data}`}
              sandbox="allow-same-origin"
              title={`${documentLabels[selectedType]} document preview`}
              srcDoc={showSources ? previewQuery.data : hideSourceReferences(previewQuery.data)}
            />
          )}
        </section>
        <aside className="preview-aside">
          <section aria-labelledby="logo-title" className="card logo-card">
            <div className="card-title-row">
              <h2 id="logo-title">Brand logo</h2>
              <span className="caption">Optional · all documents</span>
            </div>
            {logoFile || logoName ? (
              <div className="logo-file">
                <span aria-hidden="true" className="logo-placeholder">
                  LOGO
                </span>
                <div>
                  <strong>{logoFile?.name ?? logoName}</strong>
                  <span>
                    {logoFile
                      ? `${formatBytes(logoFile.size)} · ${logoFile.type.split("/")[1]?.toUpperCase() || "Image"}`
                      : "Applied to all documents"}
                  </span>
                </div>
              </div>
            ) : (
              <p className="muted">No logo uploaded.</p>
            )}
            <label className="visually-hidden" htmlFor="brand-logo-upload">
              Brand logo file
            </label>
            <input
              accept="image/png,image/jpeg,image/svg+xml"
              className="visually-hidden"
              id="brand-logo-upload"
              onChange={(event) => setLogoFile(event.target.files?.[0] ?? null)}
              ref={inputRef}
              type="file"
            />
            <div className="logo-actions">
              <Button disabled={logoMutation.isPending} onClick={() => inputRef.current?.click()}>
                {logoFile || logoName ? "Replace logo" : "Choose logo"}
              </Button>
              <Button
                disabled={!logoFile || logoMutation.isPending}
                onClick={() =>
                  logoFile && logoMutation.mutate(logoFile, { onSuccess: () => setLogoFile(null) })
                }
                variant="primary"
              >
                {logoMutation.isPending ? "Uploading…" : "Upload"}
              </Button>
              {logoName && (
                <Button
                  disabled={removeMutation.isPending}
                  onClick={() =>
                    removeMutation.mutate(undefined, { onSuccess: () => setLogoFile(null) })
                  }
                  variant="ghost"
                >
                  Remove
                </Button>
              )}
            </div>
            <p className="caption">PNG, JPG or SVG · max file size is enforced by the server.</p>
          </section>
          {check && (
            <>
              <section className="card check-card">
                <h2>Check results · {documentLabels[selectedType]}</h2>
                <dl className="check-grid">
                  <div>
                    <dt>Data coverage</dt>
                    <dd>{Math.round(check.coverage_percent)}%</dd>
                  </div>
                  <div>
                    <dt>Made-up content</dt>
                    <dd>{check.fabrication_found ? "Found" : "None"}</dd>
                  </div>
                  <div>
                    <dt>Replaced paragraphs</dt>
                    <dd>{replacedParagraphs.length}</dd>
                  </div>
                  <div>
                    <dt>Uncovered facts</dt>
                    <dd>{uncoveredFacts.length}</dd>
                  </div>
                </dl>
                {replacedParagraphs.length > 0 && (
                  <p className="caption">
                    Some generated paragraphs were removed because your data did not support them.
                    Every fact is still shown in the document.
                  </p>
                )}
              </section>
              {uncoveredFacts.length > 0 && (
                <section className="card uncovered-card">
                  <h2>Uncovered facts</h2>
                  <ul>
                    {uncoveredFacts.map((path) => (
                      <li key={path}>
                        <code>{path}</code>
                      </li>
                    ))}
                  </ul>
                  <p className="caption">Something wrong? Fix the data and generate again.</p>
                </section>
              )}
            </>
          )}
        </aside>
      </div>
      <p className="caption preview-note">
        Source references appear in the preview only. Downloaded PDFs do not include them.
      </p>
      <div className="visually-hidden" aria-live="polite">
        {showSources
          ? "Source references visible in preview."
          : "Source references remain in preview output; toggle is for reference display."}
      </div>
    </main>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function hideSourceReferences(html: string): string {
  return html.replace("</head>", "<style>.source{display:none!important}</style></head>");
}
