"use client";

import React, { useState, useEffect } from "react";
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
  HelpCircle,
  PanelLeftClose,
  PanelLeftOpen,
  MessageSquareHeart
} from "lucide-react";
import { clearAdminToken } from "@/lib/storage";

export type AdminTab = "analytics" | "triage" | "knowledge" | "settings" | "feedback";

interface AdminSidebarProps {
  activeTab: AdminTab;
  onSelectTab: (tab: AdminTab) => void;
  stats?: {
    pending_emails?: number;
    total_documents?: number;
    total_vector_chunks?: number;
    total_feedbacks?: number;
    pending_feedbacks?: number;
    autonomous_mode?: boolean;
  } | null;
  className?: string;
  onCloseMobile?: () => void;
  defaultCollapsed?: boolean;
  onCollapseChange?: (collapsed: boolean) => void;
}

export function AdminSidebar({
  activeTab,
  onSelectTab,
  stats,
  className = "",
  onCloseMobile,
  defaultCollapsed = false,
  onCollapseChange
}: AdminSidebarProps) {
  const router = useRouter();
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  // Read saved preference from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem("can_i_graduate_admin_sidebar_collapsed");
      if (saved !== null) {
        const val = saved === "true";
        setIsCollapsed(val);
        if (onCollapseChange) onCollapseChange(val);
      }
    } catch (e) {
      // Ignore in SSR
    }
  }, [onCollapseChange]);

  const toggleCollapse = () => {
    const next = !isCollapsed;
    setIsCollapsed(next);
    if (onCollapseChange) onCollapseChange(next);
    try {
      localStorage.setItem("can_i_graduate_admin_sidebar_collapsed", String(next));
    } catch (e) {
      // Ignore
    }
  };

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
    hasAlert?: boolean;
  }> = [
    {
      id: "analytics",
      label: "Analítica & Insights",
      icon: BarChart3,
      badgeColor: "bg-orange-100 text-orange-800 border-orange-200"
    },
    {
      id: "triage",
      label: "Bandeja de Triage",
      icon: Inbox,
      badge: stats?.pending_emails && stats.pending_emails > 0 ? stats.pending_emails : null,
      badgeColor: "bg-amber-100 text-amber-800 border-amber-300",
      hasAlert: Boolean(stats?.pending_emails && stats.pending_emails > 0)
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
    },
    {
      id: "feedback",
      label: "Feedbacks de Sesión",
      icon: MessageSquareHeart,
      badge: stats?.pending_feedbacks && stats.pending_feedbacks > 0
        ? stats.pending_feedbacks
        : (stats?.total_feedbacks ? `${stats.total_feedbacks}` : null),
      badgeColor: stats?.pending_feedbacks && stats.pending_feedbacks > 0
        ? "bg-rose-100 text-rose-800 border-rose-200 font-semibold"
        : "bg-stone-100 text-stone-600 border-stone-200",
      hasAlert: Boolean(stats?.pending_feedbacks && stats.pending_feedbacks > 0)
    }
  ];

  return (
    <aside
      className={`${
        isCollapsed ? "w-[72px]" : "w-64"
      } shrink-0 flex flex-col justify-between bg-[#FBFBF9] border-r border-stone-200/80 text-stone-800 selection:bg-orange-500/20 transition-all duration-300 ease-in-out select-none ${className}`}
    >
      {/* ─────────────────────────────────────────────────────────
       * Top Brand Header with Collapse Toggle
       * ───────────────────────────────────────────────────────── */}
      <div>
        <div className="p-3.5 border-b border-stone-200/70">
          {!isCollapsed ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-xl bg-orange-600 text-white flex items-center justify-center shadow-xs shrink-0">
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

              {/* Collapse button */}
              <button
                onClick={toggleCollapse}
                className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-200/60 transition shrink-0 ml-1"
                title="Colapsar menú lateral"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <div
                className="w-9 h-9 rounded-xl bg-orange-600 text-white flex items-center justify-center shadow-xs cursor-pointer"
                onClick={toggleCollapse}
                title="Can I Graduate? CRM - Clic para expandir"
              >
                <GraduationCap className="w-5 h-5" />
              </div>
              <button
                onClick={toggleCollapse}
                className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-200/60 transition"
                title="Expandir menú lateral"
              >
                <PanelLeftOpen className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* ─────────────────────────────────────────────────────────
         * Navigation Sections
         * ───────────────────────────────────────────────────────── */}
        <div className="p-2.5 space-y-5">
          {/* Main Menu Section */}
          <div className="space-y-1">
            {!isCollapsed ? (
              <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400 px-3 block">
                Menú Principal
              </span>
            ) : (
              <div className="w-7 h-px bg-stone-200/80 mx-auto my-1" />
            )}

            <div className="space-y-1 pt-0.5">
              {menuItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;

                if (isCollapsed) {
                  return (
                    <button
                      key={item.id}
                      onClick={() => handleTabClick(item.id)}
                      title={`${item.label}${item.badge ? ` (${item.badge})` : ""}`}
                      className={`w-11 h-11 mx-auto rounded-xl flex items-center justify-center relative transition-all group ${
                        isActive
                          ? "bg-stone-900 text-white shadow-xs font-semibold"
                          : "text-stone-600 hover:text-stone-900 hover:bg-stone-200/60"
                      }`}
                    >
                      <Icon
                        className={`w-4 h-4 shrink-0 ${
                          isActive ? "text-orange-400" : "text-stone-500 group-hover:text-stone-800"
                        }`}
                      />
                      {item.hasAlert && (
                        <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-orange-600 ring-2 ring-[#FBFBF9]" />
                      )}
                    </button>
                  );
                }

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
            {!isCollapsed ? (
              <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400 px-3 block">
                Portal Estudiantil
              </span>
            ) : (
              <div className="w-7 h-px bg-stone-200/80 mx-auto my-1" />
            )}

            <div className="space-y-1 pt-0.5">

              {/* Direct Student View Link */}
              {!isCollapsed ? (
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
              ) : (
                <Link
                  href="/"
                  title="Abrir Vista Estudiante (Chat)"
                  className="w-11 h-11 mx-auto rounded-xl flex items-center justify-center text-stone-600 hover:text-stone-900 hover:bg-stone-200/60 transition-all group"
                >
                  <MessageSquare className="w-4 h-4 text-orange-600 shrink-0" />
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────
       * Bottom Profile & System Status
       * ───────────────────────────────────────────────────────── */}
      <div className="p-2.5 border-t border-stone-200/70 space-y-2 bg-[#F8F7F4]/60">
        {!isCollapsed ? (
          <>
            {/* System Health Status Pill */}
            <div className="flex items-center justify-between px-3 py-2 bg-white rounded-xl border border-stone-200/80 shadow-2xs text-xs">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-[11px] font-medium text-stone-700">RAG Activo</span>
              </div>
              <span className="text-[10px] font-mono font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
                {stats?.total_vector_chunks !== undefined ? `${stats.total_vector_chunks} chunks` : "Online"}
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
          </>
        ) : (
          <div className="flex flex-col items-center gap-2 py-1">
            {/* Collapsed System Health Indicator */}
            <div
              className="w-9 h-9 rounded-xl bg-white border border-stone-200/80 flex items-center justify-center shadow-2xs cursor-pointer"
              title={`RAG Operacional: ${stats?.total_vector_chunks ?? 0} chunks indexados`}
            >
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
            </div>

            {/* Collapsed User Avatar */}
            <div
              className="w-9 h-9 rounded-full bg-orange-100 border border-orange-200 text-orange-800 font-bold text-xs flex items-center justify-center shadow-2xs cursor-pointer"
              title="Sesión activa: Admin General (canigraduateud)"
            >
              UD
            </div>

            {/* Collapsed Logout */}
            <button
              onClick={handleLogout}
              title="Cerrar sesión"
              className="w-9 h-9 rounded-xl text-stone-400 hover:text-red-600 hover:bg-red-50 flex items-center justify-center transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
