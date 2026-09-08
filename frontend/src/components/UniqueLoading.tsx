"use client";

import React from "react";
import { PixelDotsLoader } from "./ui/agent-trace";

export interface UniqueLoadingProps {
  className?: string;
  size?: "sm" | "md" | "lg";
  variant?: string;
}

export function UniqueLoading({ className }: UniqueLoadingProps) {
  return <PixelDotsLoader className={className} />;
}

export { PixelDotsLoader };
export default UniqueLoading;

