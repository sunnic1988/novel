"use client";

import {
  Activity,
  Compass,
  Globe,
  Layers,
  Megaphone,
  PenLine,
  ShieldCheck,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";

export const AGENT_ICONS: Record<string, LucideIcon> = {
  Activity,
  Compass,
  Globe,
  Layers,
  Megaphone,
  PenLine,
  ShieldCheck,
  Sparkles,
  Users,
};

export function getAgentIcon(name: string): LucideIcon {
  return AGENT_ICONS[name] || Sparkles;
}
