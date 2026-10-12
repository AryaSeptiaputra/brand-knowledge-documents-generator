export type Step = "write" | "review" | "preview";

const steps: { id: Step; label: string }[] = [
  { id: "write", label: "Write data" },
  { id: "review", label: "Review grouping" },
  { id: "preview", label: "Preview & download" },
];

export function Stepper({ active }: { active: Step }) {
  return (
    <ol aria-label="Workflow steps" className="stepper">
      {steps.map((step, index) => (
        <li className={step.id === active ? "step active" : "step"} key={step.id}>
          <span>{index + 1}</span>
          {step.label}
        </li>
      ))}
    </ol>
  );
}
