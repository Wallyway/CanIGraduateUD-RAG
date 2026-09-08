"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  GraduationCap,
  BarChart3,
  Inbox,
  Database,
  ShieldCheck,
  Send,
  MessageSquare,
  LogOut,
  Sparkles,
  Activity,
  Sliders,
  FileText,
  Search,
  CheckCircle2,
  ExternalLink,
  HelpCircle
} from "lucide-react";
import { clearAdminToken } from "@/lib/storage";

export type AdminTab = "analytics" | "triage" | "knowledge" | "settings" | "simulator";

interface AdminSidebarProps {
  activeTab: AdminTab;
  onSelectTab: (tab: AdminTab) => void;
  stats?: {
    pending_emails?: number;
    total_documents?: number;
    autonomous_mode?: boolean;
  } | null;
  className?: string;
  onCloseMobile?: () => void;
}

export function AdminSidebar({
  activeTab,
  onSelectTab,
  stats,
  className = "",
  onCloseMobile
}: AdminSidebarProps) {
  const router = useRouter();

  const handleLogout = () => {
    clearAdminToken();
    router.push("/admin/login");
  };

  const handleTabClick = (tab: AdminTab) => {
    onSelectTab(tab);
    if (onCloseMobile) onCloseMobile();
  };

  const menuItems: Array<{
    id: AdminTab;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: string | number | null;
    badgeColor?: string;
  }> = [
    {
      id: "analytics",
      label: "Analítica & Insights",
      icon: BarChart3,
      badge: "Airlytics",
      badgeColor: "bg-orange-100 text-orange-800 border-orange-200"
    },
    {
      id: "triage",
      label: "Bandeja de Triage",
      icon: Inbox,
      badge: stats?.pending_emails && stats.pending_emails > 0 ? stats.pending_emails : null,
      badgeColor: "bg-amber-100 text-amber-800 border-amber-300"
    },
    {
      id: "knowledge",
      label: "Base de Conocimiento",
      icon: Database,
      badge: stats?.total_documents ? `${stats.total_documents}` : null,
      badgeColor: "bg-stone-100 text-stone-700 border-stone-200"
    },
    {
      id: "settings",
      label: "Guardrails & Autogestión",
      icon: ShieldCheck,
      badge: stats?.autonomous_mode ? "Auto ON" : "Manual",
      badgeColor: stats?.autonomous_mode
        ? "bg-emerald-100 text-emerald-800 border-emerald-200"
        : "bg-stone-100 text-stone-600 border-stone-200"
    }
  ];

  const toolsItems: Array<{
    id: AdminTab;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: string | null;
  }> = [
    {
      id: "simulator",
      label: "Simulador de Correos",
      icon: Send,
      badge: "M365"
    }
  ];

  return (
    <aside
      className={`w-64 shrink-0 flex flex-col justify-between bg-[#FBFBF9] border-r border-stone-200/80 text-stone-800 selection:bg-orange-500/20 ${className}`}
    >
      {/* Top Brand Header */}
      <div>
        <div className="p-4 border-b border-stone-200/70">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-orange-600 text-white flex items-center justify-center shadow-xs">
              <GraduationCap className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h1 className="font-bold text-sm text-stone-900 tracking-tight truncate flex items-center gap-1.5">
                Can I Graduate?
              </h1>
              <span className="text-[11px] block font-medium text-orange-700 truncate">
                CRM Normativo UD
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Sections */}
        <div className="p-3 space-y-6">
          {/* Main Menu Section */}
          <div className="space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400 px-3 block">
              Menú Principal
            </span>
            <div className="space-y-0.5 pt-1">
              {menuItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleTabClick(item.id)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                      isActive
                        ? "bg-stone-900 text-white shadow-xs font-semibold"
                        : "text-stone-600 hover:text-stone-900 hover:bg-stone-200/60"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon
                        className={`w-4 h-4 shrink-0 ${
                          isActive ? "text-orange-400" : "text-stone-500"
                        }`}
                      />
                      <span className="truncate">{item.label}</span>
                    </div>
                    {item.badge !== null && item.badge !== undefined && (
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                          isActive
                            ? "bg-stone-800 text-stone-200 border-stone-700"
                            : item.badgeColor || "bg-stone-100 text-stone-700 border-stone-200"
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tools & External Section */}
          <div className="space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400 px-3 block">
              Herramientas RAG
            </span>
            <div className="space-y-0.5 pt-1">
              {toolsItems.map((tool) => {
                const Icon = tool.icon;
                const isActive = activeTab === tool.id;
                return (
                  <button
                    key={tool.id}
                    onClick={() => handleTabClick(tool.id)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                      isActive
                        ? "bg-stone-900 text-white shadow-xs font-semibold"
                        : "text-stone-600 hover:text-stone-900 hover:bg-stone-200/60"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon
                        className={`w-4 h-4 shrink-0 ${
                          isActive ? "text-orange-400" : "text-stone-500"
                        }`}
                      />
                      <span className="truncate">{tool.label}</span>
                    </div>
                    {tool.badge && (
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                          isActive
                            ? "bg-stone-800 text-stone-200 border-stone-700"
                            : "bg-stone-100 text-stone-600 border-stone-200"
                        }`}
                      >
                        {tool.badge}
                      </span>
                    )}
                  </button>
                );
              })}

              {/* Direct Student View Link */}
              <Link
                href="/"
                className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-stone-600 hover:text-stone-900 hover:bg-stone-200/60 transition-all group"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <MessageSquare className="w-4 h-4 text-orange-600 shrink-0" />
                  <span className="truncate">Vista Estudiante (Chat)</span>
                </div>
                <ExternalLink className="w-3.5 h-3.5 text-stone-400 group-hover:text-stone-600" />
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Profile & System Status */}
      <div className="p-3 border-t border-stone-200/70 space-y-3 bg-[#F8F7F4]/60">
        {/* System Health Status Pill */}
        <div className="flex items-center justify-between px-3 py-2 bg-white rounded-xl border border-stone-200/80 shadow-2xs text-xs">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[11px] font-medium text-stone-700">RAG Operacional</span>
          </div>
          <span className="text-[10px] font-mono font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
            98.1%
          </span>
        </div>

        {/* User Card */}
        <div className="flex items-center justify-between p-2 rounded-xl bg-white border border-stone-200/80 shadow-2xs">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-full bg-orange-100 border border-orange-200 text-orange-800 font-bold text-xs flex items-center justify-center shrink-0">
              UD
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-stone-900 truncate">Admin General</p>
              <p className="text-[10px] text-stone-500 truncate font-mono">canigraduateud</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            title="Cerrar sesión"
            className="p-1.5 rounded-lg text-stone-400 hover:text-red-600 hover:bg-red-50 transition"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}

