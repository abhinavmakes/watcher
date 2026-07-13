"use client";

import { Toaster as Sonner, type ToasterProps } from "sonner";

export function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="dark"
      position="top-center"
      richColors
      toastOptions={{
        classNames: {
          toast: "group border-border bg-card text-card-foreground shadow-lg",
        },
      }}
      {...props}
    />
  );
}
