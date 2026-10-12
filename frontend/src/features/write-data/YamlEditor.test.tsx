import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { sampleYaml } from "../../lib/sampleYaml";
import { YamlEditor } from "./YamlEditor";

function Harness() {
  const [value, setValue] = useState(sampleYaml);
  return (
    <YamlEditor
      errors={[{ message: "Expected a mapping value", line: 2, column: 3 }]}
      onChange={setValue}
      onClear={() => setValue("")}
      onSample={() => setValue(sampleYaml)}
      value={value}
    />
  );
}

describe("YamlEditor", () => {
  it("loads sample YAML and clears the editor", () => {
    render(<Harness />);
    const editor = screen.getByRole("textbox", { name: "Brand data in YAML" });
    fireEvent.click(screen.getByRole("button", { name: "Use sample data" }));
    expect(editor.textContent).toContain("Kaos Rimba");
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(editor.textContent).not.toContain("Kaos Rimba");
  });

  it("shows the server line and column and marks the editor line", () => {
    render(<Harness />);
    expect(document.querySelector(".editor-errors")).toHaveTextContent(
      "Line 2, column 3: Expected a mapping value",
    );
    expect(document.querySelector(".yaml-error-line")).toBeInTheDocument();
  });
});
