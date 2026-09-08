"use client";

import React from "react";
import { KnowledgeBaseModule } from "@/components/admin/KnowledgeBaseModule";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function AdminDocumentsPage() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Link
          href="/admin"
          className="inline-flex items-center gap-1 text-xs font-medium text-stone-500 hover:text-stone-900 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Volver al Dashboard CRM</span>
        </Link>
      </div>
      <KnowledgeBaseModule />
    </div>
  );
}

