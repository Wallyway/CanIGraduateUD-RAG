"use client";

import React, { useState, useEffect } from "react";
import {
  BarChart3,
  TrendingUp,
  Users,
  MessageSquare,
  HelpCircle,
  AlertTriangle,
  Sparkles,
  BookOpen,
  Calendar,
  CheckCircle2,
  RefreshCw,
  FilePlus2,
  ArrowUpRight,
  ShieldCheck,
  Zap,
  Info,
  Clock,
  ChevronDown,
  X,
  Activity,
  Layers,
  Check,
  Download,
  GraduationCap
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { getAdminAnalytics } from "@/lib/api";

interface AnalyticsData {
  kpis: {
    total_queries_month: number;
    previous_month_queries: number;
    query_growth_percentage: number;
    active_users_today: number;
    top_topic: string;
    rag_coverage_rate: number;
    total_all_time_queries: number;
    knowledge_gaps_rate?: number;
    avg_latency?: number;
    total_documents?: number;
    total_vector_chunks?: number;
    sistemas_queries_count?: number;
    other_faculty_queries_count?: number;
  };
  monthly_series: Array<{
    label: string;
    consultas: number;
    consultas_sistemas?: number;
    documentos: number;
    cobertura?: number;
    brechas?: number;
    tiempo?: number;
  }>;
  topic_distribution: Array<{
    topic: string;
    count: number;
    percentage: number;
  }>;
  top_questions: Array<{
    question: string;
    category: string;
    count: number;
    cited_source: string;
  }>;
  knowledge_gaps: Array<{
    id: number;
    query: string;
    category: string;
    confidence: number;
    date: string;
    status: string;
  }>;
  system_health?: {
    overall_score: number;
    success_rate: number;
    gap_rate: number;
    avg_latency: number;
    model_name: string;
    provider: string;
    total_chunks: number;
    total_documents: number;
    status: string;
  };
  other_faculty_interest?: {
    total_queries: number;
    percentage_of_all_traffic: number;
    careers_ranking: Array<{
      career: string;
      count: number;
      percentage: number;
    }>;
    recent_queries: Array<{
      id: number;
      query: string;
      career: string;
      date: string;
    }>;
  };
}

type MetricKey = "consultas" | "cobertura" | "brechas" | "tiempo";

// Micro-segmented bar mimicking frame 00:13 of reference video
function SegmentedBlockBar({
  value,
  total = 32,
  colorClass = "bg-emerald-500",
  emptyClass = "bg-stone-200/70",
}: {
  value: number;
  total?: number;
  colorClass?: string;
  emptyClass?: string;
}) {
  const activeCount = Math.max(0, Math.round((value / 100) * total));
  return (
    <div className="flex items-center gap-[3px] w-full">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`h-4 flex-1 rounded-[1.5px] transition-all duration-300 ${
            i < activeCount ? colorClass : emptyClass
          }`}
        />
      ))}
    </div>
  );
}

export function AnalyticsDashboardModule() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeMetric, setActiveMetric] = useState<MetricKey>("consultas");
  const [timeRange, setTimeRange] = useState<"6m" | "30d" | "all">("6m");
  const [isHealthModalOpen, setIsHealthModalOpen] = useState(false);
  const [activeTableTab, setActiveTableTab] = useState<"top_questions" | "gaps" | "other_careers">("top_questions");

  const fetchAnalytics = async () => {
    setIsLoading(true);
    try {
      const res = await getAdminAnalytics();
      setData(res);
    } catch (e) {
      console.error("Error cargando analítica", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  if (isLoading || !data) {
    return (
      <div className="p-20 text-center text-stone-400 bg-white rounded-2xl border border-stone-200/80 shadow-xs">
        <RefreshCw className="w-7 h-7 mx-auto mb-3 text-orange-600 animate-spin" />
        <p className="text-xs font-semibold text-stone-700">Cargando analítica y métricas del RAG...</p>
        <span className="text-[11px] text-stone-400">Procesando logs de consultas y registros de estudiantes</span>
      </div>
    );
  }

  // Real monthly series from backend
  const rawSeries = data.monthly_series || [];
  const chartSeries = (
    timeRange === "30d"
      ? rawSeries.slice(-1)
      : rawSeries
  ).map((item) => ({
    label: item.label,
    consultas: item.consultas,
    documentos: item.documentos,
    cobertura: item.cobertura ?? 0,
    brechas: item.brechas ?? 0,
    tiempo: item.tiempo ?? 0,
  }));

  const hasQueries = data.kpis.total_all_time_queries > 0;

  const metricConfigs: Record<
    MetricKey,
    {
      title: string;
      value: string;
      delta: string;
      isPositive: boolean;
      subtext: string;
      color: string;
      strokeColor: string;
      fillGradId: string;
      unit: string;
      icon: React.ComponentType<{ className?: string }>;
    }
  > = {
    consultas: {
      title: "Consultas Estudiantes",
      value: `${data.kpis.total_all_time_queries}`,
      delta: `${data.kpis.query_growth_percentage > 0 ? "+" : ""}${data.kpis.query_growth_percentage}%`,
      isPositive: data.kpis.query_growth_percentage >= 0,
      subtext: (data.kpis.other_faculty_queries_count && data.kpis.other_faculty_queries_count > 0)
        ? `${data.kpis.sistemas_queries_count ?? data.kpis.total_all_time_queries} Sistemas • ${data.kpis.other_faculty_queries_count} Otras Fac.`
        : "vs mes anterior",
      color: "text-orange-600",
      strokeColor: "#EA580C",
      fillGradId: "grad-consultas",
      unit: "consultas",
      icon: MessageSquare,
    },
    cobertura: {
      title: "Tasa Cobertura (Sistemas V1)",
      value: `${data.kpis.rag_coverage_rate}%`,
      delta: hasQueries ? "calibrado Sistemas" : "sin consultas",
      isPositive: data.kpis.rag_coverage_rate >= 80,
      subtext: `${data.kpis.sistemas_queries_count ?? data.kpis.total_all_time_queries} consultas evaluadas`,
      color: "text-blue-600",
      strokeColor: "#2563EB",
      fillGradId: "grad-cobertura",
      unit: "%",
      icon: ShieldCheck,
    },
    brechas: {
      title: "Tasa de Brechas (Sistemas V1)",
      value: `${data.kpis.knowledge_gaps_rate ?? 0}%`,
      delta: `${data.knowledge_gaps.length} normativas`,
      isPositive: (data.kpis.knowledge_gaps_rate ?? 0) === 0,
      subtext: "acuerdos faltantes en Sistemas",
      color: "text-rose-600",
      strokeColor: "#E11D48",
      fillGradId: "grad-brechas",
      unit: "%",
      icon: AlertTriangle,
    },
    tiempo: {
      title: "Tiempo de Respuesta",
      value: hasQueries ? `${data.kpis.avg_latency ?? 1.2}s` : "0.0s",
      delta: hasQueries ? "latencia inferencia" : "en reposo",
      isPositive: true,
      subtext: "tiempo medio",
      color: "text-indigo-600",
      strokeColor: "#6366F1",
      fillGradId: "grad-tiempo",
      unit: "s",
      icon: Zap,
    },
  };

  const currentMetric = metricConfigs[activeMetric];

  return (
    <div className="space-y-6">
      {/* ─────────────────────────────────────────────────────────
       * 1. HERO CARD: INTERACTIVE PERFORMANCE TREND CHART
       * Matching exact Dribbble reference video
       * ───────────────────────────────────────────────────────── */}
      <div className="bg-white border border-stone-200/90 rounded-2xl shadow-xs overflow-hidden">
        {/* Card Header with Title and Range Selector */}
        <div className="p-5 border-b border-stone-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-stone-900 tracking-tight flex items-center gap-1.5">
              Tendencia de Desempeño RAG
              <span className="text-[10px] font-medium text-stone-400 bg-stone-100 px-1.5 py-0.5 rounded">
                Live Metrics
              </span>
            </h2>
            <div
              className="p-1 text-stone-400 hover:text-stone-600 rounded-md cursor-pointer transition"
              title="Métricas dinámicas basadas en interacciones de estudiantes y respuestas del modelo"
            >
              <Info className="w-3.5 h-3.5" />
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Time range pills */}
            <div className="flex items-center bg-stone-100/90 p-0.5 rounded-xl border border-stone-200/70 text-xs">
              <button
                onClick={() => setTimeRange("6m")}
                className={`px-2.5 py-1 rounded-lg font-medium transition ${
                  timeRange === "6m"
                    ? "bg-white text-stone-900 shadow-2xs font-semibold"
                    : "text-stone-500 hover:text-stone-800"
                }`}
              >
                Últimos 6 meses
              </button>
              <button
                onClick={() => setTimeRange("30d")}
                className={`px-2.5 py-1 rounded-lg font-medium transition ${
                  timeRange === "30d"
                    ? "bg-white text-stone-900 shadow-2xs font-semibold"
                    : "text-stone-500 hover:text-stone-800"
                }`}
              >
                30 días
              </button>
              <button
                onClick={() => setTimeRange("all")}
                className={`px-2.5 py-1 rounded-lg font-medium transition ${
                  timeRange === "all"
                    ? "bg-white text-stone-900 shadow-2xs font-semibold"
                    : "text-stone-500 hover:text-stone-800"
                }`}
              >
                Año 2026
              </button>
            </div>
          </div>
        </div>

        {/* The Recharts Interactive Area Chart */}
        <div className="px-5 pt-6 pb-2">
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartSeries}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="grad-consultas" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#EA580C" stopOpacity={0.28} />
                    <stop offset="95%" stopColor="#EA580C" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="grad-cobertura" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563EB" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#2563EB" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="grad-brechas" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#E11D48" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#E11D48" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="grad-tiempo" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366F1" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#6366F1" stopOpacity={0.0} />
                  </linearGradient>
                </defs>

                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="#E7E5E4"
                />

                <XAxis
                  dataKey="label"
                  stroke="#A8A29E"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  dy={8}
                />

                <YAxis
                  stroke="#A8A29E"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  dx={-4}
                />

                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0].payload;
                      const val = item[activeMetric];
                      return (
                        <div className="bg-stone-900 text-white px-3.5 py-2.5 rounded-xl shadow-xl border border-stone-800 text-xs space-y-1">
                          <div className="flex items-center justify-between gap-3 text-[11px] text-stone-400">
                            <span>{item.label} 2026</span>
                            <span className="font-mono text-orange-400">Can I Graduate RAG</span>
                          </div>
                          <div className="flex items-center gap-2 pt-0.5">
                            <span
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: currentMetric.strokeColor }}
                            />
                            <span className="font-bold text-sm text-stone-100">
                              {val} {currentMetric.unit}
                            </span>
                          </div>
                          <p className="text-[10px] text-stone-400">{currentMetric.title}</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />

                <Area
                  type="natural"
                  dataKey={activeMetric}
                  stroke={currentMetric.strokeColor}
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill={`url(#${currentMetric.fillGradId})`}
                  activeDot={{
                    r: 6,
                    fill: currentMetric.strokeColor,
                    stroke: "#FFFFFF",
                    strokeWidth: 2,
                  }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ─────────────────────────────────────────────────────────
         * 4 Connected KPI Selector Cards Underneath Chart
         * (Clicking any card switches the active curve smoothly)
         * ───────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 border-t border-stone-100 divide-y md:divide-y-0 md:divide-x divide-stone-100 bg-stone-50/40">
          {(Object.keys(metricConfigs) as MetricKey[]).map((key) => {
            const config = metricConfigs[key];
            const isSelected = activeMetric === key;
            const Icon = config.icon;

            return (
              <button
                key={key}
                onClick={() => setActiveMetric(key)}
                className={`p-4 text-left transition-all relative flex flex-col justify-between group ${
                  isSelected
                    ? "bg-white ring-2 ring-inset ring-stone-900/5 shadow-2xs"
                    : "hover:bg-white/80"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between text-xs text-stone-500 mb-1.5">
                    <span className="flex items-center gap-1.5 font-medium truncate">
                      <Icon
                        className={`w-3.5 h-3.5 ${
                          isSelected ? config.color : "text-stone-400 group-hover:text-stone-600"
                        }`}
                      />
                      <span className={isSelected ? "text-stone-900 font-semibold" : ""}>
                        {config.title}
                      </span>
                    </span>
                  </div>

                  <div className="flex items-baseline gap-2">
                    <span className="text-xl sm:text-2xl font-bold tracking-tight text-stone-900">
                      {config.value}
                    </span>
                    <span
                      className={`text-[11px] font-semibold ${
                        config.isPositive ? "text-emerald-700" : "text-rose-600"
                      }`}
                    >
                      {config.delta}
                    </span>
                  </div>
                  <span className="text-[10px] text-stone-400 block mt-0.5">
                    {config.subtext}
                  </span>
                </div>

                {/* Bottom Active Indicator Bar */}
                {isSelected && (
                  <div
                    className="absolute bottom-0 left-0 right-0 h-0.5"
                    style={{ backgroundColor: config.strokeColor }}
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────
       * 2. BOTTOM CARDS: WORKFLOW BREAKDOWN & SYSTEM HEALTH
       * ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Left Card: Workflow breakdown (Distribución de Consultas por Categoría) */}
        <div className="bg-white border border-stone-200/90 rounded-2xl p-5 shadow-xs flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-stone-500">
                  Distribución Temática (Workflow breakdown)
                </h3>
                <div className="flex items-baseline gap-2 mt-1">
                  <span className="text-2xl font-bold text-stone-900">
                    {data.topic_distribution.length > 0 ? `${data.topic_distribution[0].percentage}%` : "0%"}
                  </span>
                  <span className="text-xs font-medium text-stone-500 truncate max-w-[200px]">
                    {data.kpis.top_topic}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-[10px] font-semibold text-stone-500">
                <span className="inline-flex items-center gap-1 bg-stone-50 text-stone-700 border border-stone-200 px-2 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                  {data.topic_distribution.length} Categorías
                </span>
              </div>
            </div>

            {/* Dynamic segmented multi-progress preview */}
            {data.topic_distribution.length > 0 ? (
              <div className="w-full h-2 rounded-full bg-stone-100 flex overflow-hidden mb-4 border border-stone-200/50">
                {data.topic_distribution.slice(0, 4).map((top, idx) => {
                  const colors = ["bg-orange-500", "bg-blue-500", "bg-amber-500", "bg-emerald-500"];
                  return (
                    <div
                      key={top.topic}
                      className={`${colors[idx % colors.length]} h-full`}
                      style={{ width: `${top.percentage}%` }}
                      title={`${top.topic}: ${top.percentage}%`}
                    />
                  );
                })}
              </div>
            ) : (
              <div className="w-full h-2 rounded-full bg-stone-100 mb-4 border border-stone-200/40" />
            )}

            {/* Rows of categories */}
            {data.topic_distribution.length > 0 ? (
              <div className="space-y-2.5 divide-y divide-stone-100 text-xs">
                {data.topic_distribution.slice(0, 5).map((topic) => (
                  <div key={topic.topic} className="pt-2 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="w-2 h-2 rounded-full bg-orange-600 shrink-0" />
                      <span className="font-medium text-stone-800 truncate">{topic.topic}</span>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div className="w-20 sm:w-28 bg-stone-100 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-stone-800 h-full rounded-full"
                          style={{ width: `${topic.percentage}%` }}
                        />
                      </div>
                      <span className="font-semibold text-stone-900 w-10 text-right font-mono">
                        {topic.percentage}%
                      </span>
                      <span className="text-[10px] font-medium text-stone-400 w-16 text-right">
                        {topic.count} {topic.count === 1 ? "consulta" : "consultas"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-stone-400 space-y-1">
                <p className="text-xs font-semibold text-stone-600">Sin consultas registradas aún</p>
                <p className="text-[11px] text-stone-400 max-w-sm mx-auto">
                  A medida que los estudiantes consulten el RAG, las temáticas se clasificarán y mostrarán automáticamente aquí.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right Card: System health (Salud del Sistema & Guardrails) */}
        <div className="bg-white border border-stone-200/90 rounded-2xl p-5 shadow-xs flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-stone-500">
                  Salud del Sistema RAG (System health)
                </h3>
                <div className="flex items-baseline gap-2 mt-1">
                  <span className="text-2xl font-bold text-stone-900">
                    {data.system_health?.overall_score ?? (hasQueries ? data.kpis.rag_coverage_rate : 100)}%
                  </span>
                  <span className="text-xs font-semibold text-emerald-600 inline-flex items-center gap-1">
                    <Check className="w-3.5 h-3.5" />
                    {data.system_health?.status || "Operacional"}
                  </span>
                </div>
              </div>

              <button
                onClick={() => setIsHealthModalOpen(true)}
                className="px-3 py-1.5 text-xs font-semibold text-stone-700 hover:text-stone-950 bg-stone-100 hover:bg-stone-200 rounded-xl border border-stone-200 transition"
              >
                Ver Detalles
              </button>
            </div>

            <p className="text-[11px] text-stone-500 mb-4">
              Monitoreo continuo de latencia OpenRouter, estado de colecciones ChromaDB y filtros de conflicto normativo.
            </p>

            {/* Mini Segmented blocks preview */}
            <div className="space-y-3 p-3.5 bg-stone-50/80 rounded-xl border border-stone-200/60">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-stone-600">Tasa de éxito con respaldo normativo</span>
                <span className="font-bold text-emerald-700 font-mono">
                  {hasQueries ? `${data.kpis.rag_coverage_rate}%` : "100% (Listo)"}
                </span>
              </div>
              <SegmentedBlockBar
                value={hasQueries ? data.kpis.rag_coverage_rate : 100}
                total={30}
                colorClass="bg-emerald-500"
              />

              <div className="flex items-center justify-between text-xs pt-1">
                <span className="font-medium text-stone-600">Tasa de brechas de conocimiento</span>
                <span className="font-bold text-stone-700 font-mono">
                  {data.kpis.knowledge_gaps_rate ?? 0}%
                </span>
              </div>
              <SegmentedBlockBar
                value={Math.max(0, data.kpis.knowledge_gaps_rate ?? 0)}
                total={30}
                colorClass="bg-rose-500"
              />
            </div>
          </div>

          <div className="pt-2 flex items-center justify-between text-[11px] text-stone-500 border-t border-stone-100">
            <span>
              Latencia promedio:{" "}
              <strong className="text-stone-800 font-mono">
                {hasQueries ? `${data.kpis.avg_latency ?? 1.2}s` : "0.0s"}
              </strong>
            </span>
            <span>
              ChromaDB chunks:{" "}
              <strong className="text-stone-800 font-mono">
                {data.kpis.total_vector_chunks ?? data.system_health?.total_chunks ?? 0}
              </strong>
            </span>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────
       * 3. TABBED REAL STUDENT QUESTIONS & KNOWLEDGE GAPS
       * ───────────────────────────────────────────────────────── */}
      <div className="bg-white border border-stone-200/90 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-stone-100 pb-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTableTab("top_questions")}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition ${
                activeTableTab === "top_questions"
                  ? "bg-stone-900 text-white shadow-xs"
                  : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
              }`}
            >
              Top Preguntas Frecuentes ({data.top_questions.length})
            </button>
            <button
              onClick={() => setActiveTableTab("gaps")}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
                activeTableTab === "gaps"
                  ? "bg-rose-950 text-rose-200 shadow-xs border border-rose-800/80"
                  : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
              <span>Brechas en Sistemas ({data.knowledge_gaps.length})</span>
            </button>
            <button
              onClick={() => setActiveTableTab("other_careers")}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
                activeTableTab === "other_careers"
                  ? "bg-indigo-950 text-indigo-200 shadow-xs border border-indigo-800/80"
                  : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
              }`}
            >
              <GraduationCap className="w-3.5 h-3.5 text-indigo-400" />
              <span>Demanda Otras Facultades ({data.other_faculty_interest?.total_queries ?? 0})</span>
            </button>
          </div>
        </div>

        {activeTableTab === "top_questions" && (
          <div>
            {data.top_questions.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-stone-500 border-b border-stone-100 bg-stone-50/50">
                    <tr>
                      <th className="py-2.5 px-3 font-semibold">Pregunta Real del Estudiante</th>
                      <th className="py-2.5 px-3 font-semibold">Categoría</th>
                      <th className="py-2.5 px-3 font-semibold">Frecuencia</th>
                      <th className="py-2.5 px-3 font-semibold">Respaldo Normativo</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 text-stone-700">
                    {data.top_questions.map((q, idx) => (
                      <tr key={idx} className="hover:bg-stone-50/60 transition">
                        <td className="py-3 px-3 font-medium text-stone-900 max-w-md">
                          {q.question}
                        </td>
                        <td className="py-3 px-3">
                          <span className="px-2 py-0.5 rounded-full bg-stone-100 text-stone-700 text-[10px] font-medium border border-stone-200">
                            {q.category}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-mono font-semibold text-stone-800">
                          {q.count} {q.count === 1 ? "consulta" : "consultas"}
                        </td>
                        <td className="py-3 px-3 text-stone-500">
                          <span className="inline-flex items-center gap-1 text-orange-700 font-medium">
                            <BookOpen className="w-3 h-3 text-orange-600 shrink-0" />
                            {q.cited_source}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-12 text-center text-stone-400 space-y-1.5 bg-stone-50/50 rounded-xl border border-dashed border-stone-200">
                <HelpCircle className="w-7 h-7 mx-auto text-stone-300" />
                <p className="text-xs font-semibold text-stone-700">No hay consultas de estudiantes registradas aún</p>
                <p className="text-[11px] text-stone-400 max-w-md mx-auto">
                  A medida que los estudiantes realicen preguntas en el portal sobre modalidades, pasantías y grados, se consolidarán automáticamente en este ranking.
                </p>
              </div>
            )}
          </div>
        )}

        {activeTableTab === "gaps" && (
          <div className="space-y-3">
            <p className="text-xs text-stone-500">
              Estas preguntas tuvieron baja confianza o no contaron con un artículo oficial en la base vectorial. Te recomendamos cargar la resolución correspondiente en la pestaña <strong>Base de Conocimiento</strong>.
            </p>
            {data.knowledge_gaps.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-stone-500 border-b border-stone-100 bg-rose-50/30">
                    <tr>
                      <th className="py-2.5 px-3 font-semibold">Consulta no resuelta</th>
                      <th className="py-2.5 px-3 font-semibold">Categoría</th>
                      <th className="py-2.5 px-3 font-semibold">Confianza RAG</th>
                      <th className="py-2.5 px-3 font-semibold">Fecha</th>
                      <th className="py-2.5 px-3 font-semibold">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 text-stone-700">
                    {data.knowledge_gaps.map((gap) => (
                      <tr key={gap.id} className="hover:bg-rose-50/20 transition">
                        <td className="py-3 px-3 font-medium text-stone-900 max-w-md">
                          {gap.query}
                        </td>
                        <td className="py-3 px-3">
                          <span className="px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 text-[10px] font-semibold">
                            {gap.category}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-mono font-bold text-rose-600">
                          {gap.confidence}%
                        </td>
                        <td className="py-3 px-3 text-stone-400 text-[11px]">
                          {gap.date}
                        </td>
                        <td className="py-3 px-3">
                          <span className="text-[10px] font-medium text-stone-500">
                            Requiere Resolución
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-12 text-center text-stone-400 space-y-1.5 bg-emerald-50/30 rounded-xl border border-dashed border-emerald-200">
                <CheckCircle2 className="w-7 h-7 mx-auto text-emerald-500" />
                <p className="text-xs font-semibold text-emerald-800">No se registran brechas de conocimiento</p>
                <p className="text-[11px] text-stone-500 max-w-md mx-auto">
                  Todas las consultas de los estudiantes cuentan con respaldo suficiente en la base de conocimiento normativo.
                </p>
              </div>
            )}
          </div>
        )}

        {activeTableTab === "other_careers" && (
          <div className="space-y-4">
            <div className="p-4 bg-indigo-50/70 border border-indigo-100 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800 text-[10px] font-bold uppercase tracking-wider border border-indigo-200">
                    Fase Piloto V1
                  </span>
                  <h4 className="text-xs font-bold text-indigo-950">
                    Interés y Demanda de Expansión a Otras Facultades
                  </h4>
                </div>
                <p className="text-[11px] text-indigo-900/80 max-w-2xl leading-relaxed">
                  Las métricas de cobertura y confianza del RAG evalúan exclusivamente a <strong>Ingeniería de Sistemas</strong>. Las consultas de otros programas son interceptadas amigablemente por el guardrail institucional sin penalizar el modelo, y se registran aquí para medir qué carreras tienen mayor demanda de incorporación.
                </p>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <div className="text-center px-3 py-1.5 bg-white rounded-xl border border-indigo-200/80 shadow-2xs">
                  <div className="text-lg font-bold text-indigo-950 font-mono">
                    {data.other_faculty_interest?.total_queries ?? 0}
                  </div>
                  <div className="text-[10px] font-medium text-stone-500">Consultas Recibidas</div>
                </div>
                <div className="text-center px-3 py-1.5 bg-white rounded-xl border border-indigo-200/80 shadow-2xs">
                  <div className="text-lg font-bold text-indigo-600 font-mono">
                    {data.other_faculty_interest?.percentage_of_all_traffic ?? 0}%
                  </div>
                  <div className="text-[10px] font-medium text-stone-500">Del Tráfico Total</div>
                </div>
              </div>
            </div>

            {/* Ranking de carreras interesadas */}
            {data.other_faculty_interest && data.other_faculty_interest.careers_ranking.length > 0 && (
              <div className="space-y-2">
                <h5 className="text-[11px] font-bold text-stone-600 uppercase tracking-wider">
                  Programas Académicos Interesados
                </h5>
                <div className="flex flex-wrap gap-2">
                  {data.other_faculty_interest.careers_ranking.map((item, idx) => (
                    <div
                      key={idx}
                      className="px-3 py-1.5 bg-stone-50 hover:bg-stone-100 rounded-xl border border-stone-200 flex items-center gap-2 text-xs transition"
                    >
                      <span className="font-semibold text-stone-900">{item.career}</span>
                      <span className="px-1.5 py-0.5 rounded-md bg-stone-200 text-stone-700 text-[10px] font-mono font-bold">
                        {item.count} {item.count === 1 ? "consulta" : "consultas"} ({item.percentage}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tabla de consultas de otras facultades */}
            {data.other_faculty_interest && data.other_faculty_interest.recent_queries.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-stone-500 border-b border-stone-100 bg-indigo-50/30">
                    <tr>
                      <th className="py-2.5 px-3 font-semibold">Consulta del Estudiante</th>
                      <th className="py-2.5 px-3 font-semibold">Carrera / Facultad Detectada</th>
                      <th className="py-2.5 px-3 font-semibold">Fecha y Hora</th>
                      <th className="py-2.5 px-3 font-semibold">Acción del Guardrail</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 text-stone-700">
                    {data.other_faculty_interest.recent_queries.map((q) => (
                      <tr key={q.id} className="hover:bg-indigo-50/20 transition">
                        <td className="py-3 px-3 font-medium text-stone-900 max-w-md">
                          {q.query}
                        </td>
                        <td className="py-3 px-3">
                          <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 text-[10px] font-semibold">
                            {q.career}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-stone-400 text-[11px] font-mono">
                          {q.date}
                        </td>
                        <td className="py-3 px-3">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 text-[10px] font-semibold border border-emerald-200">
                            <Check className="w-3 h-3" />
                            Redirección Amigable Realizada
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-12 text-center text-stone-400 space-y-1.5 bg-stone-50/50 rounded-xl border border-dashed border-stone-200">
                <GraduationCap className="w-7 h-7 mx-auto text-stone-300" />
                <p className="text-xs font-semibold text-stone-700">No se registran consultas de otras carreras</p>
                <p className="text-[11px] text-stone-400 max-w-md mx-auto">
                  Cuando estudiantes de otras facultades consulten el portal, sus preguntas y programas aparecerán registrados aquí.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────
       * 4. SYSTEM HEALTH MODAL / DIALOG (FRAME 00:13 REFERENCE)
       * Detailed breakdown of system performance with segmented bars
       * ───────────────────────────────────────────────────────── */}
      {isHealthModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fadeIn">
          <div className="relative w-full max-w-lg bg-white rounded-3xl border border-stone-200/90 shadow-2xl p-6 space-y-5 animate-scaleUp">
            <div className="flex items-start justify-between border-b border-stone-100 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center">
                    <Activity className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-stone-900">Salud Integral del Sistema RAG</h3>
                    <p className="text-[11px] text-stone-500">
                      Desglose del motor vectorial y generación de respuestas con IA
                    </p>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setIsHealthModalOpen(false)}
                className="p-1 text-stone-400 hover:text-stone-700 rounded-lg hover:bg-stone-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Top Score */}
            <div className="p-4 bg-stone-50 rounded-2xl border border-stone-200/60 flex items-center justify-between">
              <div>
                <span className="text-xs text-stone-500 font-medium block">Puntuación General</span>
                <span className="text-3xl font-extrabold text-stone-900">
                  {data.system_health?.overall_score ?? (hasQueries ? data.kpis.rag_coverage_rate : 100)}%
                </span>
                <span className="text-[11px] text-emerald-600 font-semibold block mt-0.5">
                  ↑ Motor RAG {data.system_health?.status || "Operacional"}
                </span>
              </div>
              <div className="text-right text-[11px] text-stone-500 font-mono space-y-0.5">
                <div>Model: {data.system_health?.model_name || "Sin modelo configurado"}</div>
                <div>Motor: {data.system_health?.provider?.toUpperCase() || "OPENROUTER"}</div>
                <div>Vector: ChromaDB Persistent ({data.kpis.total_vector_chunks ?? 0} chunks)</div>
                <div>Documentos: {data.kpis.total_documents ?? 0} acuerdos activos</div>
              </div>
            </div>

            {/* Segmented Details */}
            <div className="space-y-4 text-xs">
              {/* Metric 1 */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-stone-800">Success Rate (Respuestas con Respaldo)</span>
                  <span className="font-bold font-mono text-emerald-600">
                    {hasQueries ? `${data.kpis.rag_coverage_rate}%` : "100% (Listo)"}
                  </span>
                </div>
                <SegmentedBlockBar
                  value={hasQueries ? data.kpis.rag_coverage_rate : 100}
                  total={32}
                  colorClass="bg-emerald-500"
                />
                <span className="text-[11px] text-stone-400 block">
                  {hasQueries
                    ? "Porcentaje de consultas estudiantiles respaldadas con citas normativas válidas."
                    : "El sistema está activo y a la espera de las primeras consultas de los estudiantes."}
                </span>
              </div>

              {/* Metric 2 */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-stone-800">Failure / Gap Rate (Brechas Detectadas)</span>
                  <span className="font-bold font-mono text-rose-600">
                    {data.kpis.knowledge_gaps_rate ?? 0}%
                  </span>
                </div>
                <SegmentedBlockBar
                  value={data.kpis.knowledge_gaps_rate ?? 0}
                  total={32}
                  colorClass="bg-rose-500"
                />
                <span className="text-[11px] text-stone-400 block">
                  {data.knowledge_gaps.length > 0
                    ? `${data.knowledge_gaps.length} consultas sin suficiente respaldo normativo que requieren indexar nuevas resoluciones.`
                    : "No se registran brechas normativas actualmente."}
                </span>
              </div>

              {/* Metric 3 */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-stone-800">Average Run Time (Tiempo de Inferencia)</span>
                  <span className="font-bold font-mono text-indigo-600">
                    {hasQueries ? `${data.kpis.avg_latency ?? 1.2}s` : "0.0s"}
                  </span>
                </div>
                <SegmentedBlockBar
                  value={hasQueries ? 80 : 0}
                  total={32}
                  colorClass="bg-indigo-500"
                />
                <span className="text-[11px] text-stone-400 block">
                  Latencia promedio de generación medida sobre el pipeline RAG y streaming SSE.
                </span>
              </div>
            </div>

            {/* Footer */}
            <div className="pt-2 flex justify-end border-t border-stone-100">
              <button
                onClick={() => setIsHealthModalOpen(false)}
                className="px-5 py-2 bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold rounded-xl transition"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
