import { type DocumentType, documentLabels } from "../../api/client";

export function GeneratingStatus({
  activeTypes,
  error,
}: {
  activeTypes: DocumentType[];
  error: string | null;
}) {
  return (
    <main className="generating-page">
      <section aria-live="polite" className="generating-card">
        <div>
          <h1>{error ? "Generation failed" : "Generating documents"}</h1>
          <p>
            {error ??
              "Each section is written from your data, then checked against it. This can take a few minutes."}
          </p>
        </div>
        <ul className="generation-list">
          {activeTypes.map((type) => (
            <li key={type}>
              <div className="generation-row">
                <span>
                  <span aria-hidden="true" className="document-icon" />
                  {documentLabels[type]}
                </span>
                <span className={error ? "error-text" : "muted"}>
                  {error ? "Needs attention" : "In progress…"}
                </span>
              </div>
              <div
                aria-label={`${documentLabels[type]} generation`}
                className={error ? "progress-track failed" : "progress-track indeterminate"}
                role="progressbar"
              />
            </li>
          ))}
        </ul>
        <div className="phase-list">
          <span className="phase-active">Compose</span>
          <span>Check content</span>
          <span>Render preview</span>
        </div>
        {error && (
          <p className="recovery-hint">
            Your data and grouping are still available. Go back, check the data, and try again.
          </p>
        )}
      </section>
    </main>
  );
}
