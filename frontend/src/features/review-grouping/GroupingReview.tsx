import {
  type CompletenessSuggestion,
  type DocumentType,
  documentLabels,
  documentTypes,
  type Grouping,
  type GroupingEntry,
} from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";

function kindLabel(entry: GroupingEntry): string {
  if (entry.unit_kind === "PRODUCT_SIZE") return "Product size";
  if (entry.unit_kind === "PRODUCT") return "Product";
  return "General";
}

export function GroupingReview({
  brandName,
  sectionCount,
  productCount,
  grouping,
  suggestions,
  busy,
  onToggle,
  onBack,
  onGenerate,
}: {
  brandName: string;
  sectionCount: number;
  productCount: number;
  grouping: Grouping;
  suggestions: CompletenessSuggestion[];
  busy: boolean;
  onToggle: (section: string, type: DocumentType, selected: boolean) => void;
  onBack: () => void;
  onGenerate: () => void;
}) {
  return (
    <main className="main-content">
      <div className="page-heading-row">
        <div className="page-heading">
          <h1>Review document grouping</h1>
          <p>
            Choose which documents each data section goes into. One section can go into more than
            one document.
          </p>
          <p className="caption">
            Suggested by rules: general sections → Policy; guide keywords such as “how to”, “care”,
            and “size” → Guide; products → Product Knowledge.
          </p>
        </div>
        <dl className="summary-stats">
          <div>
            <dt>Brand</dt>
            <dd>{brandName}</dd>
          </div>
          <div>
            <dt>Sections</dt>
            <dd>{sectionCount}</dd>
          </div>
          <div>
            <dt>Products</dt>
            <dd>{productCount}</dd>
          </div>
        </dl>
      </div>
      <div className="content-columns">
        <section aria-label="Document grouping" className="table-card">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Data section</th>
                  <th scope="col">Kind</th>
                  {documentTypes.map((type) => (
                    <th className="center" key={type} scope="col">
                      {documentLabels[type]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grouping.entries.map((entry) => (
                  <tr key={entry.section}>
                    <th className="path-cell" scope="row">
                      <code>{entry.section.replaceAll(".", " › ")}</code>
                    </th>
                    <td>
                      <span className="chip">{kindLabel(entry)}</span>
                    </td>
                    {documentTypes.map((type) => (
                      <td className="center checkbox-cell" key={type}>
                        <Checkbox
                          aria-label={`Include ${entry.section} in ${documentLabels[type]}`}
                          checked={entry.document_types.includes(type)}
                          disabled={busy}
                          onCheckedChange={(checked) =>
                            onToggle(entry.section, type, checked === true)
                          }
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {grouping.entries.length === 0 && (
            <p className="empty-state">No document sections were found in this data.</p>
          )}
        </section>
        <aside aria-labelledby="suggestions-title" className="card suggestions-card">
          <div>
            <h2 id="suggestions-title">Completeness suggestions</h2>
            <p className="caption">Shown to you only. Not included in the documents.</p>
          </div>
          {suggestions.length > 0 ? (
            <ul className="suggestion-list">
              {suggestions.map((suggestion) => (
                <li key={`${suggestion.related_path}-${suggestion.message}`}>
                  <span>{suggestion.message}</span>
                  {suggestion.related_path && <code>{suggestion.related_path}</code>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-state">No suggestions for this data.</p>
          )}
          <button className="text-link" onClick={onBack} type="button">
            Edit data to add missing facts
          </button>
        </aside>
      </div>
      <div className="page-actions">
        <Button onClick={onBack}>Back to data</Button>
        <Button
          disabled={busy || grouping.entries.every((entry) => entry.document_types.length === 0)}
          onClick={onGenerate}
          variant="primary"
        >
          Generate documents
        </Button>
      </div>
    </main>
  );
}
