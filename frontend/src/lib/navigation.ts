import {
  FlaskConical,
  LayoutDashboard,
  MessageSquare,
  FileText,
  Layers,
  Network,
  Package,
  Settings,
  Shield,
  type LucideIcon,
} from "lucide-react";

export type NavRouteId =
  | "chat"
  | "dashboard"
  | "policies"
  | "contracts"
  | "change-packs"
  | "domain-packs"
  | "systems"
  | "demo"
  | "settings";

export interface NavItem {
  id: NavRouteId;
  label: string;
  href: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { id: "chat", label: "Chat", href: "/", icon: MessageSquare },
  { id: "dashboard", label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { id: "policies", label: "Policies", href: "/policies", icon: Shield },
  { id: "contracts", label: "Contracts", href: "/contracts", icon: FileText },
  { id: "change-packs", label: "Change Packs", href: "/change-packs", icon: Package },
  { id: "domain-packs", label: "Domain Packs", href: "/domain-packs", icon: Layers },
  { id: "systems", label: "System Graph", href: "/systems", icon: Network },
  { id: "demo", label: "Demo Workflow", href: "/demo", icon: FlaskConical },
  { id: "settings", label: "Settings", href: "/settings", icon: Settings },
];
