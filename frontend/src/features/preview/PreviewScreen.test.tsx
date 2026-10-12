import { describe, expect, it } from "vitest";
import { fitFrameToContent } from "./PreviewScreen";

describe("fitFrameToContent", () => {
  it("sets the frame height to the height of its document", () => {
    const frame = document.createElement("iframe");
    document.body.append(frame);
    const root = frame.contentDocument?.documentElement;
    if (!root) throw new Error("The test frame has no document.");
    Object.defineProperty(root, "scrollHeight", { configurable: true, value: 1234 });

    fitFrameToContent(frame);

    expect(frame.style.height).toBe("1234px");
    frame.remove();
  });
});
