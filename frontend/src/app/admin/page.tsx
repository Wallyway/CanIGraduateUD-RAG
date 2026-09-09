"use client";

import React, { Suspense, useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Inbox,
  Database,
  BarChart3,
  ShieldCheck,
  Mail,
  Send,
  RefreshCw,
  Sparkles,
  ExternalLink,
  ChevronRight,
  Layers,
  CheckCircle2,
  Filter
} from "lucide-react";
import Link from "next/link";
import { getAdminStats } from "@/lib/api";
import { EmailTriageModule } from "@/components/admin/EmailTriageModule";
import { KnowledgeBaseModule } from "@/components/admin/KnowledgeBaseModule";
import { AnalyticsDashboardModule } from "@/components/admin/AnalyticsDashboardModule";
import { SettingsGuardrailsModule } from "@/components/admin/SettingsGuardrailsModule";
import { SessionFeedbackModule } from "@/components/admin/SessionFeedbackModule";

type TabKey = "analytics" | "triage" | "knowledge" | "settings" | "feedback";

function AdminDashboardContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const tabParam = searchParams.get("tab") as TabKey | null;
  const [activeTab, setActiveTab] = useState<TabKey>(tabParam || "analytics");
  const [stats, setStats] = useState<{
    pending_emails: number;
    total_documents: number;
    total_vector_chunks: number;
    total_feedbacks?: number;
    pending_feedbacks?: number;
    autonomous_mode: boolean;
  } | null>(null);

  const fetchStats = async () => {
    try {
      const data = await getAdminStats();
      setStats(data);
    } catch (e) {
      console.error("Error fetching admin stats", e);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  useEffect(() => {
    if (tabParam && ["analytics", "triage", "knowledge", "settings", "feedback"].includes(tabParam)) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  const handleTabChange = (key: TabKey) => {
    setActiveTab(key);
    router.replace(`/admin?tab=${key}`, { scroll: false });
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Active Module Container */}
      <div className="transition-opacity duration-200">
        {activeTab === "analytics" && (
          <AnalyticsDashboardModule />
        )}
        {activeTab === "triage" && (
          <EmailTriageModule onDataChanged={fetchStats} />
        )}
        {activeTab === "knowledge" && (
          <KnowledgeBaseModule />
        )}
        {activeTab === "settings" && (
          <SettingsGuardrailsModule />
        )}
        {activeTab === "feedback" && (
          <SessionFeedbackModule />
        )}
      </div>
    </div>
  );
}

export default function AdminDashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="py-24 text-center space-y-3">
          <div className="w-3 h-3 rounded-full bg-orange-600 animate-ping mx-auto" />
          <p className="text-xs text-stone-500 font-medium">
            Cargando plataforma CRM Can I Graduate UD...
          </p>
        </div>
      }
    >
      <AdminDashboardContent />
    </Suspense>
  );
}
