import { defaultKeymap, indentWithTab } from "@codemirror/commands";
import { yaml } from "@codemirror/lang-yaml";
import { EditorState, StateEffect, StateField } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  highlightActiveLine,
  keymap,
  lineNumbers,
} from "@codemirror/view";
import { useEffect, useRef } from "react";
import type { ErrorDetail } from "../../api/client";
import { Button } from "../../components/ui/Button";

const setErrorLines = StateEffect.define<number[]>();

const diagnosticsField = StateField.define<number[]>({
  create: () => [],
  update: (lines, transaction) =>
    transaction.effects.reduce(
      (current, effect) => (effect.is(setErrorLines) ? effect.value : current),
      transaction.docChanged ? [] : lines,
    ),
});

const errorLines = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update: (decorations, transaction) => {
    const hasNewDiagnostics = transaction.effects.some((effect) => effect.is(setErrorLines));
    if (!transaction.docChanged && !hasNewDiagnostics) return decorations;
    const diagnostics = transaction.state.field(diagnosticsField);
    return Decoration.set(
      diagnostics.flatMap((line) => {
        const lineNumber = Math.min(Math.max(line, 1), transaction.state.doc.lines);
        return [
          Decoration.line({ class: "yaml-error-line" }).range(
            transaction.state.doc.line(lineNumber).from,
          ),
        ];
      }),
    );
  },
  provide: (field) => EditorView.decorations.from(field),
});

export function YamlEditor({
  value,
  errors,
  onChange,
  onSample,
  onClear,
}: {
  value: string;
  errors: ErrorDetail[];
  onChange: (value: string) => void;
  onSample: () => void;
  onClear: () => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const latestOnChange = useRef(onChange);
  const latestValue = useRef(value);
  latestOnChange.current = onChange;
  latestValue.current = value;

  useEffect(() => {
    if (!host.current) return;
    const editor = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: latestValue.current,
        extensions: [
          yaml(),
          EditorState.tabSize.of(2),
          lineNumbers(),
          highlightActiveLine(),
          keymap.of([...defaultKeymap, indentWithTab]),
          diagnosticsField,
          errorLines,
          EditorView.updateListener.of((update) => {
            if (update.docChanged) latestOnChange.current(update.state.doc.toString());
          }),
          EditorView.contentAttributes.of({ "aria-label": "Brand data in YAML" }),
          EditorView.theme({
            "&": { height: "100%", fontSize: "13px" },
            ".cm-scroller": {
              overflow: "auto",
              fontFamily: "IBM Plex Mono, monospace",
              lineHeight: "26px",
            },
            ".cm-content": { padding: "12px 16px", minHeight: "520px" },
            ".cm-gutters": {
              backgroundColor: "#f7f7f5",
              borderRight: "1px solid #e6e6e2",
              color: "#8a8a84",
            },
            ".cm-line": { padding: "0" },
          }),
        ],
      }),
    });
    view.current = editor;
    return () => {
      editor.destroy();
      view.current = null;
    };
  }, []);

  useEffect(() => {
    const editor = view.current;
    if (!editor) return;
    if (editor.state.doc.toString() !== value) {
      editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: value } });
    }
  }, [value]);

  useEffect(() => {
    view.current?.dispatch({
      effects: setErrorLines.of(
        errors.map((error) => error.line).filter((line): line is number => line != null),
      ),
    });
  }, [errors]);

  return (
    <section aria-label="YAML editor" className="editor-card">
      <div className="editor-toolbar">
        <span>
          Brand data <span className="muted">· YAML</span>
        </span>
        <div className="toolbar-actions">
          <Button className="small-button" onClick={onSample} type="button">
            Use sample data
          </Button>
          <Button className="small-button" onClick={onClear} type="button" variant="ghost">
            Clear
          </Button>
        </div>
      </div>
      <div className="editor-host" ref={host} />
      {errors.length > 0 && (
        <div aria-live="assertive" className="editor-errors">
          {errors.map((error) => (
            <p key={`${error.line}-${error.column}-${error.message}`}>
              Line {error.line ?? "?"}
              {error.column ? `, column ${error.column}` : ""}: {error.message}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
