import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { api } from "./api/client";

vi.mock("./api/client", async (loadActual) => {
  const actual = await loadActual<typeof import("./api/client")>();
  return { ...actual, api: { POST: vi.fn(), PATCH: vi.fn() } };
});

const entry = {
  section: "retur",
  unit_kind: "GENERAL_SECTION" as const,
  document_types: ["POLICY" as const],
  changed_by_user: false,
};

const analyzed = {
  session_id: "session-1",
  brand_name: "Kaos Rimba",
  grouping: { entries: [entry], confirmed_by_user: false },
  suggestions: [{ message: "Add warranty details", related_path: "garansi" }],
};

function documentOf(type: "POLICY" | "GUIDE" | "PRODUCT_KNOWLEDGE") {
  return { document_type: type, title: type, brand_name: "Kaos Rimba", sections: [] };
}

const generated = {
  documents: [documentOf("POLICY")],
  check_results: [
    {
      document_type: "POLICY" as const,
      coverage_percent: 100,
      fabrication_found: false,
      replaced_paragraphs: [],
      uncovered_facts: [],
    },
  ],
};

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

function requestUrl(input: Request | string): string {
  return input instanceof Request ? input.url : String(input);
}

function requests(): { url: string; method: string }[] {
  return vi.mocked(fetch).mock.calls.map(([input, init]) => ({
    url: requestUrl(input as Request | string),
    method: input instanceof Request ? input.method : (init?.method ?? "GET"),
  }));
}

function response<T>(data: T) {
  return { data, error: undefined, response: new Response() };
}

describe("App workflow", () => {
  beforeEach(() => {
    vi.mocked(api.POST).mockReset();
    vi.mocked(api.PATCH).mockReset();
    vi.mocked(api.POST).mockImplementation((path) => {
      if (path === "/api/analyze") return Promise.resolve(response(analyzed)) as never;
      return Promise.resolve(response(generated)) as never;
    });
    vi.mocked(api.PATCH).mockImplementation(
      () =>
        Promise.resolve(
          response({
            entries: [{ ...entry, document_types: ["POLICY", "GUIDE"] }],
            confirmed_by_user: true,
          }),
        ) as never,
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: Request | string, init?: RequestInit) => {
        const url = requestUrl(input);
        const method = input instanceof Request ? input.method : init?.method;
        if (url.includes("/api/logo") && method === "PUT")
          return new Response('{"file_name":"brand.png","media_type":"image/png"}', {
            headers: { "Content-Type": "application/json" },
          });
        if (url.includes("/api/logo") && method === "DELETE")
          return new Response(null, { status: 204 });
        if (url.includes("/api/documents/") && url.endsWith("/pdf?session_id=session-1"))
          return new Response("%PDF-fake");
        return new Response(
          '<html><head></head><body><div class="source">retur.batas</div></body></html>',
          { headers: { "Content-Type": "text/html" } },
        );
      }),
    );
  });

  it("checks sample data, updates grouping, generates, previews, and requests a PDF download", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Use sample data" }));
    fireEvent.click(screen.getByRole("button", { name: "Check data and continue" }));
    expect(
      await screen.findByRole("heading", { name: "Review document grouping" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "Include retur in Guide" }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "Include retur in Guide" })).toBeChecked(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Generate documents" }));
    expect(await screen.findByRole("tab", { name: "Policy" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));
    await waitFor(() =>
      expect(requests()).toContainEqual({
        url: expect.stringContaining("/api/documents/policy/pdf?session_id=session-1"),
        method: "GET",
      }),
    );
    expect(await screen.findByText("100%")).toBeInTheDocument();
  });

  it("uploads, replaces, and removes an optional logo and toggles preview references", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Use sample data" }));
    fireEvent.click(screen.getByRole("button", { name: "Check data and continue" }));
    fireEvent.click(await screen.findByRole("button", { name: "Generate documents" }));
    const iframe = await screen.findByTitle("Policy document preview");
    expect(iframe).toHaveAttribute("srcdoc", expect.stringContaining('class="source"'));

    fireEvent.click(screen.getByRole("checkbox", { name: "Show source references" }));
    await waitFor(() =>
      expect(iframe).toHaveAttribute(
        "srcdoc",
        expect.stringContaining(".source{display:none!important}"),
      ),
    );

    const file = new File(["logo"], "brand.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Brand logo file"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText("Applied to all documents")).toBeInTheDocument();
    expect(requests()).toContainEqual({
      url: expect.stringContaining("/api/logo?session_id=session-1"),
      method: "PUT",
    });
    const upload = vi
      .mocked(fetch)
      .mock.calls.map(([input]) => input)
      .find((input): input is Request => input instanceof Request && input.method === "PUT");
    expect(upload?.headers.get("content-type")).toMatch(/^multipart\/form-data/);
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() =>
      expect(requests()).toContainEqual({
        url: expect.stringContaining("/api/logo?session_id=session-1"),
        method: "DELETE",
      }),
    );
  });

  it("shows validation errors with their YAML location", async () => {
    vi.mocked(api.POST).mockImplementationOnce(
      () =>
        Promise.resolve({
          data: undefined,
          error: { errors: [{ message: "Invalid indentation", line: 3, column: 5 }] },
          response: new Response(null, { status: 422 }),
        }) as never,
    );
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Use sample data" }));
    fireEvent.click(screen.getByRole("button", { name: "Check data and continue" }));
    expect(await screen.findByText("Line 3, column 5: Invalid indentation")).toBeInTheDocument();
  });

  it("includes suggestions in the review and can return to edit data", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Use sample data" }));
    fireEvent.click(screen.getByRole("button", { name: "Check data and continue" }));
    expect(await screen.findByText("Add warranty details")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back to data" }));
    expect(screen.getByRole("heading", { name: "Write your brand data" })).toBeInTheDocument();
  });

  it("shows preview tabs only for documents the backend generated", async () => {
    const sizeOnly = {
      ...analyzed,
      grouping: {
        entries: [
          {
            section: "product.kaos boxy",
            unit_kind: "PRODUCT" as const,
            document_types: ["PRODUCT_KNOWLEDGE" as const],
            changed_by_user: false,
          },
          {
            section: "product.kaos boxy.size",
            unit_kind: "PRODUCT_SIZE" as const,
            document_types: ["GUIDE" as const],
            changed_by_user: true,
          },
        ],
        confirmed_by_user: true,
      },
    };
    vi.mocked(api.POST).mockImplementation((path) => {
      if (path === "/api/analyze") return Promise.resolve(response(sizeOnly)) as never;
      return Promise.resolve(
        response({
          documents: [documentOf("GUIDE")],
          check_results: [{ ...generated.check_results[0], document_type: "GUIDE" as const }],
        }),
      ) as never;
    });
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Use sample data" }));
    fireEvent.click(screen.getByRole("button", { name: "Check data and continue" }));
    fireEvent.click(await screen.findByRole("button", { name: "Generate documents" }));

    expect(await screen.findByRole("tab", { name: "Guide" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Product Knowledge" })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(requests()).toContainEqual({
        url: expect.stringContaining("/api/documents/guide/preview?session_id=session-1"),
        method: "GET",
      }),
    );
    expect(requests().some(({ url }) => url.includes("/product_knowledge/preview"))).toBe(false);
  });

  it("shows located YAML errors once, without a global notice", async () => {
    vi.mocked(api.POST).mockImplementationOnce(
      () =>
        Promise.resolve({
          data: undefined,
          error: { errors: [{ message: "Invalid indentation", line: 3, column: 5 }] },
          response: new Response(null, { status: 422 }),
        }) as never,
    );
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Use sample data" }));
    fireEvent.click(screen.getByRole("button", { name: "Check data and continue" }));
    expect(await screen.findByText("Line 3, column 5: Invalid indentation")).toBeInTheDocument();
    expect(document.querySelector(".global-notice")).toBeNull();
    expect(screen.getByText("We couldn't read this YAML.")).toBeInTheDocument();
  });

  it("reports an expired session when changing the grouping", async () => {
    vi.mocked(api.PATCH).mockImplementationOnce(
      () =>
        Promise.resolve({
          data: undefined,
          error: { errors: [{ message: "Session not found." }] },
          response: new Response(null, { status: 404 }),
        }) as never,
    );
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Use sample data" }));
    fireEvent.click(screen.getByRole("button", { name: "Check data and continue" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: "Include retur in Guide" }));
    expect(
      await screen.findByText("Your session expired. Submit your data again."),
    ).toBeInTheDocument();
  });
});
