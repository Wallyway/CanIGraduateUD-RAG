"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  Cpu,
  Sliders,
  AlertTriangle,
  Lock,
  CheckCircle2,
  RefreshCw,
  Save,
  Info,
  Layers,
  Sparkles,
  MailCheck
} from "lucide-react";
import { getAdminSettings, updateAdminSettings } from "@/lib/api";

export function SettingsGuardrailsModule() {
  const [autonomousMode, setAutonomousMode] = useState(false);
  const [threshold, setThreshold] = useState(85);
  const [requireUdDomain, setRequireUdDomain] = useState(true);
  const [conflictGuardrail, setConflictGuardrail] = useState(true);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setIsLoading(true);
    try {
      const cfg = await getAdminSettings();
      setAutonomousMode(Boolean(cfg.autonomous_mode));
      setThreshold(typeof cfg.autonomous_threshold === "number" ? cfg.autonomous_threshold : 85);
      setRequireUdDomain(Boolean(cfg.require_ud_domain));
      setConflictGuardrail(Boolean(cfg.conflict_guardrail));
    } catch (e) {
      console.error("Error cargando configuración", e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateAdminSettings({
        autonomous_mode: autonomousMode,
        autonomous_threshold: threshold,
        require_ud_domain: requireUdDomain,
        conflict_guardrail: conflictGuardrail,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e: any) {
      alert("Error guardando configuración: " + e.message);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-16 text-center text-stone-400 bg-white rounded-2xl border border-stone-200">
        <RefreshCw className="w-8 h-8 mx-auto mb-2 text-[#C2410C] animate-spin" />
        <p className="text-sm font-medium">Cargando configuración de guardrails...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-stone-900 tracking-tight flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-[#C2410C]" />
            Configuración & Guardrails de Autogestión
          </h2>
          <p className="text-xs sm:text-sm text-stone-500 mt-0.5">
            Establece los límites y reglas de seguridad para la ingesta autónoma de comunicados por IA.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={isSaving}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition shadow-xs disabled:opacity-50"
        >
          {isSaving ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Save className="w-3.5 h-3.5" />
          )}
          <span>{isSaving ? "Guardando..." : "Guardar Guardrails"}</span>
        </button>
      </div>

      {saveSuccess && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>Configuración y políticas de guardrails guardadas exitosamente.</span>
        </div>
      )}

      {/* Autonomous Mode Master Switch */}
      <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-xs space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-[#C2410C]" />
              <h3 className="text-sm font-bold text-stone-900">
                Modo Autónomo de Ingestión (Agéntico)
              </h3>
            </div>
            <p className="text-xs text-stone-500 leading-relaxed max-w-xl">
              Cuando está activo, el agente LLM puede auto-indexar comunicados oficiales en ChromaDB de forma automática siempre que superen el umbral de confianza y cumplan todos los guardrails de seguridad.
            </p>
          </div>

          <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={autonomousMode}
              onChange={(e) => setAutonomousMode(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-stone-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-stone-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#C2410C]"></div>
          </label>
        </div>

        <div className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
          autonomousMode ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-stone-50 text-stone-600 border border-stone-200"
        }`}>
          {autonomousMode ? (
            <>
              <Sparkles className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>
                <strong>Modo Autónomo Activo:</strong> Los comunicados con score mayor o igual al umbral y remitente verificado se indexan de inmediato.
              </span>
            </>
          ) : (
            <>
              <Lock className="w-4 h-4 text-stone-400 shrink-0" />
              <span>
                <strong>Modo Supervisado (Human-in-the-Loop):</strong> Todo comunicado permanecerá en estado "Pendiente" hasta que un administrador lo apruebe manualmente.
              </span>
            </>
          )}
        </div>
      </div>

      {/* Threshold Slider Card */}
      <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-[#C2410C]" />
            <h3 className="text-sm font-bold text-stone-900">
              Umbral Mínimo de Confianza IA para Auto-Indexación
            </h3>
          </div>
          <span className="text-sm font-bold font-mono px-3 py-1 rounded-full bg-amber-50 text-[#C2410C] border border-amber-200">
            {threshold}% Relevancia
          </span>
        </div>

        <p className="text-xs text-stone-500 leading-relaxed">
          Si la evaluación de relevancia del agente es inferior a este porcentaje, el comunicado se derivará obligatoriamente a revisión humana.
        </p>

        <div className="pt-2 space-y-2">
          <input
            type="range"
            min="50"
            max="100"
            step="1"
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="w-full h-2 bg-stone-200 rounded-lg appearance-none cursor-pointer accent-[#C2410C]"
          />
          <div className="flex justify-between text-[11px] text-stone-400 font-mono">
            <span>50% (Permisivo)</span>
            <span className="text-[#C2410C] font-semibold">85% (Recomendado)</span>
            <span>100% (Estricto)</span>
          </div>
        </div>
      </div>

      {/* Security Guardrails */}
      <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-xs space-y-5">
        <div className="flex items-center gap-2 pb-3 border-b border-stone-100">
          <ShieldCheck className="w-4 h-4 text-[#C2410C]" />
          <h3 className="text-sm font-bold text-stone-900">
            Guardrails de Seguridad Normativa
          </h3>
        </div>

        {/* Guardrail 1: Institutional Domain */}
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <MailCheck className="w-4 h-4 text-stone-700" />
              <h4 className="text-xs font-bold text-stone-900">
                Filtro Estricto de Dominio Institucional (@udistrital.edu.co)
              </h4>
            </div>
            <p className="text-xs text-stone-500 leading-relaxed">
              Solo se permite la auto-indexación si el correo proviene del dominio oficial de la Universidad Distrital. Correos de dominios externos (Gmail, Yahoo, etc.) requerirán siempre validación humana manual, incluso si superan el 85%.
            </p>
          </div>

          <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={requireUdDomain}
              onChange={(e) => setRequireUdDomain(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-10 h-5 bg-stone-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-stone-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#C2410C]"></div>
          </label>
        </div>

        {/* Guardrail 2: Conflict & Derogation Detection */}
        <div className="flex items-start justify-between gap-4 pt-3 border-t border-stone-100">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <h4 className="text-xs font-bold text-stone-900">
                Detección de Derogaciones y Conflictos Normativos
              </h4>
            </div>
            <p className="text-xs text-stone-500 leading-relaxed">
              Si un comunicado contiene palabras clave de modificación normativa ("deroga", "derógase", "modifica acuerdo", "deja sin efecto"), se pausa la auto-indexación y se exige confirmación humana para evitar sobreescribir acuerdos vigentes sin supervisión.
            </p>
          </div>

          <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={conflictGuardrail}
              onChange={(e) => setConflictGuardrail(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-10 h-5 bg-stone-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-stone-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#C2410C]"></div>
          </label>
        </div>
      </div>

      {/* Security & Anti-Abuse Defense (3 Strikes / 24h Ban) Section */}
      <div className="bg-white p-6 rounded-2xl border border-stone-200 shadow-xs space-y-5">
        <div className="flex items-center justify-between pb-3 border-b border-stone-100">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-red-600" />
            <div>
              <h3 className="text-sm font-bold text-stone-900">
                Defensa Anti-Prompting, Rate Limiting & 3 Strikes (24h)
              </h3>
              <p className="text-xs text-stone-500 mt-0.5">
                Regla estricta de protección de tokens: 3 strikes por consultas no académicas conllevan suspensión de 24 horas por IP, subred y dispositivo.
              </p>
            </div>
          </div>
          <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-red-50 text-red-700 border border-red-200">
            3 Strikes = 24h Ban
          </span>
        </div>

        {/* Protection Explanatory Badges */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="p-3.5 rounded-xl bg-stone-50 border border-stone-200">
            <span className="text-[11px] font-bold text-stone-500 uppercase tracking-wider block mb-1">
              Filtro 0 Tokens
            </span>
            <p className="text-xs text-stone-800 font-medium">
              Intercepción inmediata en FastAPI sin invocar LLM ni base vectorial para consultas abusivas o prompt injections.
            </p>
          </div>
          <div className="p-3.5 rounded-xl bg-stone-50 border border-stone-200">
            <span className="text-[11px] font-bold text-stone-500 uppercase tracking-wider block mb-1">
              Multi-Factor Client Ban
            </span>
            <p className="text-xs text-stone-800 font-medium">
              Bloqueo simultáneo por IP real, Subred /24 (anti-salto de red) y UUID persistente de dispositivo.
            </p>
          </div>
          <div className="p-3.5 rounded-xl bg-stone-50 border border-stone-200">
            <span className="text-[11px] font-bold text-stone-500 uppercase tracking-wider block mb-1">
              Rate Limit Volumétrico
            </span>
            <p className="text-xs text-stone-800 font-medium">
              Ventana deslizante (Sliding Window): máx. 10 consultas/min en chat, 5 en feedback y 5 intentos en login.
            </p>
          </div>
        </div>

        {/* Technical Architecture Note */}
        <div className="p-3.5 rounded-xl bg-amber-50/70 border border-amber-200 text-xs text-amber-900 leading-relaxed">
          <strong>Arquitectura de Red y Privacidad L2/L3:</strong> Las direcciones físicas MAC residen en la Capa 2 (Enlace de Datos) y son eliminadas por los enrutadores al atravesar Internet por protocolo TCP/IP. En su lugar, el sistema implementa la defensa equivalente web de alta fidelidad: <strong>Huella/UUID de Dispositivo en LocalStorage + Dirección IP Pública + Subred /24 + User-Agent</strong>.
        </div>
      </div>
    </div>
  );
}

export default SettingsGuardrailsModule;


