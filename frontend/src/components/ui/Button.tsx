import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

// Sizes and colors follow docs/design/ui-ux/tokens.md, "Components and sizes".
const buttonVariants = cva(
  "button inline-flex min-h-11 cursor-pointer items-center justify-center rounded-lg border text-body transition-colors disabled:cursor-not-allowed disabled:opacity-disabled",
  {
    variants: {
      variant: {
        primary:
          "button-primary border-ink bg-ink px-5.5 font-medium text-surface hover:enabled:bg-ink-subtle",
        secondary:
          "button-secondary border-line-strong bg-surface px-4 text-ink hover:enabled:bg-gutter",
        ghost: "button-ghost border-transparent bg-transparent px-4 text-ink-tertiary",
      },
    },
    defaultVariants: { variant: "secondary" },
  },
);

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

export function Button({ variant, className, type = "button", ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant }), className)} type={type} {...props} />;
}
