import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "../../lib/utils";

export function Checkbox({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      className={cn(
        "inline-flex size-5 shrink-0 cursor-pointer items-center justify-center rounded-xs border border-ink bg-surface align-middle text-surface data-[state=checked]:bg-ink disabled:cursor-wait",
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator>
        <svg aria-hidden="true" className="size-3.5" fill="none" viewBox="0 0 16 16">
          <path d="M3 8.5 6.5 12 13 4.5" stroke="currentColor" strokeWidth="2" />
        </svg>
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}
