"use client";

import React, { useEffect, useState, Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AdminSidebar, AdminTab } from "@/components/admin/AdminSidebar";
import { getAdminToken } from "@/lib/storage";
import { getAdminStats } from "@/lib/api";
import {
  Menu,
  X,
  Search,
  Mail,
  Send,
  MessageSquare,
  Sparkles,
  ChevronRight,
  Bell,
  Download,
  GraduationCap
} from "lucide-react";
import Link from "next/link";

function AdminLayoutInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [stats, setStats] = useState<{
    pending_emails?: number;
    total_documents?: number;
    autonomous_mode?: boolean;
  } | null>(null);

  // Authentication check
  useEffect(() => {
    if (pathname === "/admin/login") {
      setIsAuthorized(true);
      return;
    }

    const token = getAdminToken();
    if (!token) {
      router.push("/admin/login");
    } else {
      setIsAuthorized(true);
    }
  }, [pathname, router]);

  // Fetch admin stats for sidebar badges
  const fetchStats = async () => {
    try {
      const data = await getAdminStats();
      setStats(data);
    } catch (e) {
      console.error("Error cargando estadísticas para sidebar", e);
    }
  };

  useEffect(() => {
    if (isAuthorized && pathname !== "/admin/login") {
      fetchStats();
    }
  }, [isAuthorized, pathname]);

  // Determine current active tab
  let activeTab: AdminTab = "analytics";
  if (pathname === "/admin/documents") {
    activeTab = "knowledge";
  } else {
    const tabParam = searchParams.get("tab") as AdminTab | null;
    if (tabParam && ["analytics", "triage", "knowledge", "settings"].includes(tabParam)) {
      activeTab = tabParam;
    }
  }

  const handleSelectTab = (tab: AdminTab) => {
    router.push(`/admin?tab=${tab}`);
    setIsMobileSidebarOpen(false);
  };

  if (pathname === "/admin/login") {
    return <>{children}</>;
  }

  if (isAuthorized === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAF8F5] text-stone-600">
        <div className="flex items-center gap-2.5 text-sm font-medium">
          <div className="w-2.5 h-2.5 rounded-full bg-orange-600 animate-ping" />
          <span>Verificando credenciales de administrador...</span>
        </div>
      </div>
    );
  }

  const tabLabels: Record<AdminTab, string> = {
    analytics: "Analítica & Insights",
    triage: "Bandeja de Triage",
    knowledge: "Base de Conocimiento",
    settings: "Guardrails & Autogestión",
  };

  return (
    <div className="min-h-screen bg-[#FAF8F5] text-stone-900 flex selection:bg-orange-500/20 selection:text-orange-950 font-sans">
      {/* ─────────────────────────────────────────────────────────
       * DESKTOP FIXED SIDEBAR
       * ───────────────────────────────────────────────────────── */}
      <div className="hidden md:flex h-screen sticky top-0 z-30">
        <AdminSidebar
          activeTab={activeTab}
          onSelectTab={handleSelectTab}
          stats={stats}
        />
      </div>

      {/* ─────────────────────────────────────────────────────────
       * MOBILE DRAWER SIDEBAR
       * ───────────────────────────────────────────────────────── */}
      {isMobileSidebarOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={() => setIsMobileSidebarOpen(false)}
          />
          <div className="relative flex-1 flex flex-col max-w-xs w-full bg-[#FBFBF9] shadow-2xl z-10 animate-slideRight">
            <div className="absolute top-3 right-3">
              <button
                onClick={() => setIsMobileSidebarOpen(false)}
                className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 bg-stone-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <AdminSidebar
              activeTab={activeTab}
              onSelectTab={handleSelectTab}
              stats={stats}
              className="w-full h-full border-r-0"
              onCloseMobile={() => setIsMobileSidebarOpen(false)}
            />
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────
       * MAIN CONTENT AREA + TOPBAR
       * ───────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen overflow-x-hidden">
        {/* Sleek Topbar Header matching video */}
        <header className="sticky top-0 z-20 h-16 bg-white/85 backdrop-blur-md border-b border-stone-200/80 px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            {/* Mobile Hamburger */}
            <button
              onClick={() => setIsMobileSidebarOpen(true)}
              className="md:hidden p-2 rounded-xl text-stone-600 hover:text-stone-900 hover:bg-stone-100 transition shrink-0"
              title="Abrir menú"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Breadcrumb & View Title */}
            <div className="flex items-center gap-2 text-xs text-stone-500 truncate">
              <span className="font-semibold text-stone-800 hidden sm:inline">CRM Normativo</span>
              <ChevronRight className="w-3.5 h-3.5 text-stone-300 hidden sm:inline" />
              <span className="font-bold text-stone-900 bg-stone-100 px-2.5 py-1 rounded-lg border border-stone-200/70 truncate">
                {tabLabels[activeTab] || "Dashboard"}
              </span>
            </div>
          </div>

          {/* Quick Search & Actions */}
          <div className="flex items-center gap-2.5 shrink-0">
            {/* Student View Shortcut */}
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-stone-50 text-stone-700 text-xs font-semibold rounded-xl border border-stone-200/90 transition shadow-2xs"
              title="Abrir interfaz de chat de estudiantes"
            >
              <MessageSquare className="w-3.5 h-3.5 text-orange-600" />
              <span className="hidden lg:inline">Chat Estudiante</span>
            </Link>

            {/* Notification indicator */}
            <div
              className="p-2 text-stone-400 hover:text-stone-700 rounded-xl hover:bg-stone-100 transition cursor-pointer relative"
              title="Notificaciones del sistema"
            >
              <Bell className="w-4 h-4" />
              {stats?.pending_emails && stats.pending_emails > 0 ? (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-orange-600" />
              ) : null}
            </div>
          </div>
        </header>

        {/* Dynamic Page Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-[#FAF8F5] text-stone-600">
          <div className="flex items-center gap-2.5 text-sm font-medium">
            <div className="w-2.5 h-2.5 rounded-full bg-orange-600 animate-ping" />
            <span>Cargando entorno CRM Can I Graduate UD...</span>
          </div>
        </div>
      }
    >
      <AdminLayoutInner>{children}</AdminLayoutInner>
    </Suspense>
  );
}
