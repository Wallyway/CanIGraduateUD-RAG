"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { GraduationCap, Inbox, Database, BarChart3, ShieldCheck, Send, LogOut, MessageSquare } from "lucide-react";
import { clearAdminToken } from "@/lib/storage";

export const AdminNavbar: React.FC = () => {
  const pathname = usePathname();
  const router = useRouter();

  if (pathname === "/admin/login") {
    return null;
  }

  const handleLogout = () => {
    clearAdminToken();
    router.push("/admin/login");
  };

  const navLinks = [
    { href: "/admin?tab=triage", label: "Triage", icon: Inbox },
    { href: "/admin?tab=knowledge", label: "Base Normativa", icon: Database },
    { href: "/admin?tab=analytics", label: "Analítica", icon: BarChart3 },
    { href: "/admin?tab=settings", label: "Guardrails", icon: ShieldCheck },
    { href: "/admin/simulator", label: "Simulador", icon: Send },
  ];

  return (
    <header className="bg-white/90 border-b border-stone-200/80 sticky top-0 z-30 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/admin" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-xl bg-orange-600 text-white flex items-center justify-center shadow-sm group-hover:bg-orange-700 transition">
              <GraduationCap className="w-4 h-4" />
            </div>
            <div>
              <span className="font-bold text-stone-900 text-sm tracking-tight flex items-center gap-1.5">
                Can I Graduate UD?
                <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 border border-orange-200">CRM</span>
              </span>
              <span className="text-[11px] block text-stone-500 font-medium">
                Gestión Normativa & RAG
              </span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-1.5">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    isActive
                      ? "bg-orange-50 text-orange-700 border border-orange-200 font-semibold shadow-xs"
                      : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{link.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-2.5">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium text-stone-700 hover:text-stone-950 bg-white hover:bg-stone-50 border border-stone-200 shadow-xs transition"
          >
            <MessageSquare className="w-3.5 h-3.5 text-orange-600" />
            <span className="hidden sm:inline">Vista Estudiante</span>
          </Link>
          <button
            onClick={handleLogout}
            title="Cerrar sesión"
            className="p-2 rounded-xl text-stone-400 hover:text-red-600 hover:bg-red-50 border border-transparent hover:border-red-100 transition"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};

