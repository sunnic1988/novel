"use client";

import {
  Compass,
  Globe,
  PenLine,
  ShieldCheck,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";

export const AGENT_ICONS: Record<string, LucideIcon> = {
  Compass,
  Globe,
  PenLine,
  ShieldCheck,
  Sparkles,
  Users,
};

export function getAgentIcon(name: string): LucideIcon {
  return AGENT_ICONS[name] || Sparkles;
}
