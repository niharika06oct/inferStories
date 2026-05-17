"use client";

import * as React from "react";

export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export function Panel({
  title,
  description,
  children,
  className,
  compact,
  eyebrow,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  compact?: boolean;
  eyebrow?: string;
}) {
  return (
    <section className={cn("flex flex-col", compact ? "gap-2.5" : "gap-4", className)}>
      <div>
        {eyebrow ? (
          <p className="text-[11px] font-medium tracking-wide text-muted-foreground">
            {eyebrow}
          </p>
        ) : null}
        <h2 className={cn("soft-heading font-semibold text-foreground", compact ? "text-sm" : "text-base")}>
          {title}
        </h2>
        {description ? (
          <p
            className={cn(
              "text-muted-foreground",
              compact ? "mt-0.5 text-xs leading-5" : "mt-1 text-sm leading-6",
            )}
          >
            {description}
          </p>
        ) : null}
      </div>
      {children}
    </section>
  );
}

export function FieldLabel({ children }: { children: React.ReactNode }) {
  return <span className="text-sm font-medium text-foreground">{children}</span>;
}

export function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("glass-panel rounded-[var(--radius-card)]", className)}>
      {children}
    </div>
  );
}

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "flex h-9 w-full rounded-md border border-input bg-card/40 px-3 py-1 text-sm text-foreground shadow-sm transition-colors",
        "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function Textarea({
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "flex min-h-[90px] w-full resize-y rounded-md border border-input bg-card/40 px-3 py-2 text-sm text-foreground shadow-sm transition-colors",
        "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function Button({
  variant = "default",
  size = "default",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "secondary" | "outline" | "ghost" | "destructive" | "cta";
  size?: "default" | "sm";
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md text-sm font-medium transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
        size === "default" && "h-9 px-3",
        size === "sm" && "h-8 px-2.5 text-xs",
        variant === "default" &&
          "bg-primary text-primary-foreground shadow-sm hover:opacity-95",
        variant === "cta" &&
          "bg-cta text-cta-foreground shadow-sm hover:opacity-95",
        variant === "secondary" &&
          "bg-secondary text-secondary-foreground hover:opacity-90",
        variant === "outline" &&
          "border border-input bg-card/30 hover:bg-accent hover:text-accent-foreground",
        variant === "ghost" && "hover:bg-accent hover:text-accent-foreground",
        variant === "destructive" &&
          "bg-destructive text-destructive-foreground hover:opacity-90",
        className,
      )}
      {...props}
    />
  );
}

export function Badge({
  variant = "default",
  children,
}: {
  variant?:
    | "default"
    | "secondary"
    | "outline"
    | "destructive"
    | "warning"
    | "success";
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold",
        variant === "default" &&
          "border-transparent bg-primary text-primary-foreground",
        variant === "secondary" &&
          "border-transparent bg-secondary text-secondary-foreground",
        variant === "outline" &&
          "border-border bg-transparent text-foreground",
        variant === "destructive" &&
          "border-destructive/30 bg-destructive/10 text-destructive",
        variant === "warning" &&
          "border-warning/40 bg-warning/15 text-warning",
        variant === "success" &&
          "border-success/30 bg-success/10 text-success",
      )}
    >
      {children}
    </span>
  );
}

export function Alert({
  variant = "destructive",
  title,
  children,
}: {
  variant?: "destructive";
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "glass-panel rounded-[var(--radius-card)] border px-4 py-3 text-sm",
        variant === "destructive" &&
          "border-destructive/30 bg-destructive/10 text-foreground",
      )}
    >
      <p className="font-semibold text-destructive">{title}</p>
      <div className="mt-1 text-muted-foreground">{children}</div>
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
      aria-hidden
    />
  );
}
