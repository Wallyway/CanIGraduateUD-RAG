"use client";

import React, { useState } from "react";
import { Send, Sparkles, CheckCircle2, AlertTriangle, ArrowRight, Bot, Mail, Paperclip, Loader2 } from "lucide-react";
import Link from "next/link";
import { simulateEmail } from "@/lib/api";

const PRESETS = [
  {
    name: "Convocatoria Modalidades de Grado 2026-1 (Relevante)",
    sender: "proyectocurricularsistemas@udistrital.edu.co",
    subject: "Comunicado No. 012 - Apertura Inscripción Modalidades de Grado Ingeniería de Sistemas 2026-1",
    body: `Estimados estudiantes de Ingeniería de Sistemas:

El Comité de Currículo del Proyecto Curricular de Ingeniería de Sistemas informa que a partir del próximo lunes se abre el periodo oficial para la radicación de propuestas de modalidad de grado (Monografía, Pasantía Institucional y Asignaturas de Posgrado) correspondientes al periodo 2026-1.

Requisitos recordatorios:
1. Pasantía: Requiere el 80% de créditos aprobados y promedio acumulado no inferior a 3.2 [Acuerdo 038 de 2015].
2. Asignaturas de Posgrado: Requiere el 85% de créditos y promedio mínimo de 3.8.
3. Fecha límite de radicación: 15 de marzo de 2026.

Adjuntamos el formato oficial de anteproyecto y la circular informativa.

Cordialmente,
Coordinación Proyecto Curricular de Ingeniería de Sistemas
Facultad de Ingeniería - Universidad Distrital`,
    attachments: ["circular_012_modalidades_2026.pdf", "formato_anteproyecto_sistemas.docx"],
  },
  {
    name: "Fechas de Paz y Salvo y Ceremonia (Relevante)",
    sender: "secretariaingenieria@udistrital.edu.co",
    subject: "Circular 008 - Cronograma de Grados Colectivos y Paz y Salvos 2026-1",
    body: `A la comunidad estudiantil de la Facultad de Ingeniería:

Se publica el cronograma oficial de grados colectivos para los programas de pregrado de la Facultad de Ingeniería:
- Recepción de carpetas de grado en el sistema Cóndor: del 2 al 12 de abril de 2026.
- Verificación de paz y salvos (Biblioteca, Laboratorios, ILUD B2): del 13 al 20 de abril de 2026.
- Ceremonia solemne de graduación: 30 de mayo de 2026 en el Auditorio Mayor Sabio Caldas.

Recuerden que para tramitar el paz y salvo de biblioteca deben haber subido la monografía en formato institucional al RIUD.

Secretaría Académica
Facultad de Ingeniería - UD`,
    attachments: ["cronograma_grados_colectivos_2026.pdf"],
  },
  {
    name: "Torneo Deportivo Docente (No Relevante)",
    sender: "bienestar@udistrital.edu.co",
    subject: "Convocatoria al Torneo de Microfútbol para Docentes y Administrativos 2026",
    body: `Bienestar Institucional invita a todo el personal administrativo y docente de la Universidad Distrital a inscribir sus equipos en el torneo relámpago de microfútbol que se llevará a cabo en la sede Aduanilla de Paiba. Las inscripciones estarán abiertas hasta el viernes.`,
    attachments: [],
  },
];

const AdminSimulatorPage: React.FC = () => {
  const [sender, setSender] = useState(PRESETS[0].sender);
  const [subject, setSubject] = useState(PRESETS[0].subject);
  const [body, setBody] = useState(PRESETS[0].body);
  const [attachmentsText, setAttachmentsText] = useState(PRESETS[0].attachments.join(", "));

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any | null>(null);

  const handleApplyPreset = (preset: typeof PRESETS[0]) => {
    setSender(preset.sender);
    setSubject(preset.subject);
    setBody(preset.body);
    setAttachmentsText(preset.attachments.join(", "));
    setResult(null);
  };

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setResult(null);

    const attList = attachmentsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      const res = await simulateEmail({
        sender,
        subject,
        body,
        attachments: attList,
      });
      setResult(res);
    } catch (err: any) {
      alert("Error simulando el correo: " + err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100 tracking-tight">
          Simulador de Correos y Comunicados M365
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 mt-1">
          Prueba de extremo a extremo cómo el sistema recibe, clasifica con el LLM e indexa comunicados como si llegaran desde la cuenta institucional de Microsoft 365.
        </p>
      </div>

      {/* Preset Selector */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block">
          Seleccionar Caso de Prueba Rápido:
        </label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
          {PRESETS.map((p, i) => (
            <button
              key={i}
              type="button"
              onClick={() => handleApplyPreset(p)}
              className="text-left p-3 rounded-xl bg-zinc-900 hover:bg-zinc-800/90 border border-zinc-800 hover:border-zinc-700 transition space-y-1"
            >
              <span className="text-xs font-semibold text-zinc-200 block truncate">
                {p.name}
              </span>
              <span className="text-[11px] text-zinc-500 block truncate font-mono">
                {p.subject}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Form Column */}
        <div className="lg:col-span-7 bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 text-zinc-100 font-semibold text-base border-b border-zinc-800 pb-3">
            <Mail className="w-5 h-5 text-amber-400" />
            <h2>Detalles del Correo Entrante Simulado</h2>
          </div>

          <form onSubmit={handleSimulate} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">
                Remitente Institucional (From)
              </label>
              <input
                type="text"
                required
                value={sender}
                onChange={(e) => setSender(e.target.value)}
                placeholder="decanaturaingenieria@udistrital.edu.co"
                className="w-full bg-zinc-950 border border-zinc-800 focus:border-red-600 rounded-xl py-2 px-3 text-xs text-zinc-200 outline-none font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">
                Asunto del Correo (Subject)
              </label>
              <input
                type="text"
                required
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Comunicado oficial sobre fechas de grado..."
                className="w-full bg-zinc-950 border border-zinc-800 focus:border-red-600 rounded-xl py-2 px-3 text-xs text-zinc-200 outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">
                Archivos Adjuntos Simulados (separados por coma)
              </label>
              <div className="relative">
                <Paperclip className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={attachmentsText}
                  onChange={(e) => setAttachmentsText(e.target.value)}
                  placeholder="circular_01.pdf, cronograma.pdf"
                  className="w-full bg-zinc-950 border border-zinc-800 focus:border-red-600 rounded-xl py-2 pl-9 pr-3 text-xs text-zinc-200 outline-none font-mono"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">
                Cuerpo del Correo (Body)
              </label>
              <textarea
                rows={8}
                required
                value={body}
                onChange={(e) => setBody(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 focus:border-red-600 rounded-xl p-3 text-xs text-zinc-200 outline-none font-mono leading-relaxed"
              />
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                disabled={isLoading}
                className="px-5 py-2.5 bg-red-800 hover:bg-red-700 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition flex items-center gap-2 shadow-sm cursor-pointer"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                <span>Simular Recepción y Ejecutar Triage LLM</span>
              </button>
            </div>
          </form>
        </div>

        {/* Real-time Triage Output Column */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center gap-2 text-zinc-100 font-semibold text-base border-b border-zinc-800 pb-3">
              <Bot className="w-5 h-5 text-amber-400" />
              <h2>Evaluación en Tiempo Real</h2>
            </div>

            {isLoading ? (
              <div className="text-center py-16 space-y-3">
                <div className="w-4 h-4 rounded-full bg-amber-400 animate-ping mx-auto" />
                <p className="text-xs text-zinc-400 font-mono">
                  Agente LLM analizando pertinencia con la Facultad de Ingeniería...
                </p>
              </div>
            ) : result ? (
              <div className="space-y-4 animate-fadeIn">
                <div
                  className={`p-4 rounded-xl border flex items-start gap-3 ${
                    result.is_relevant
                      ? "bg-emerald-950/40 border-emerald-800/60"
                      : "bg-zinc-950 border-zinc-800"
                  }`}
                >
                  {result.is_relevant ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  )}
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-zinc-100 text-sm">
                        {result.is_relevant
                          ? "COMUNICADO RELEVANTE"
                          : "COMUNICADO NO RELEVANTE"}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-zinc-800 text-amber-400 font-mono">
                        {result.relevance_score}%
                      </span>
                    </div>
                    <span className="text-[11px] block font-mono text-zinc-400">
                      Estado: <strong>{result.status}</strong>
                    </span>
                  </div>
                </div>

                <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-4 space-y-2 text-xs">
                  <div>
                    <span className="text-amber-400 text-[10px] uppercase font-bold tracking-wider block">
                      Resumen Generado por el LLM:
                    </span>
                    <p className="text-zinc-200 mt-1 leading-relaxed">
                      {result.triage_summary}
                    </p>
                  </div>

                  {result.triage_reasoning && (
                    <div className="pt-2 border-t border-zinc-800/60">
                      <span className="text-zinc-500 text-[10px] uppercase font-bold tracking-wider block">
                        Razón del Veredicto:
                      </span>
                      <p className="text-zinc-400 mt-0.5 italic">
                        {result.triage_reasoning}
                      </p>
                    </div>
                  )}
                </div>

                <div className="pt-2 flex flex-col sm:flex-row gap-2">
                  <Link
                    href="/admin"
                    className="flex-1 py-2 px-3 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition text-center"
                  >
                    <span>Ir a Bandeja de Triage</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                  <Link
                    href="/"
                    className="flex-1 py-2 px-3 rounded-xl bg-red-900/80 hover:bg-red-800 text-amber-300 text-xs font-semibold flex items-center justify-center gap-1.5 transition text-center"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Preguntar en el Chat</span>
                  </Link>
                </div>
              </div>
            ) : (
              <div className="text-center py-16 text-zinc-500 text-xs space-y-2">
                <Send className="w-6 h-6 mx-auto text-zinc-600 opacity-60" />
                <p>
                  Selecciona una plantilla o escribe un correo y presiona el botón para ver el resultado de la clasificación.
                </p>
              </div>
            )}
          </div>

          {/* Integration instructions card */}
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-2xl p-5 text-xs text-zinc-400 space-y-2.5">
            <h3 className="font-semibold text-zinc-200 text-xs flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Conexión con Microsoft Power Automate</span>
            </h3>
            <p className="leading-relaxed">
              En tu cuenta de estudiante de la Universidad Distrital:
            </p>
            <ol className="list-decimal list-inside space-y-1 font-mono text-[11px] text-zinc-400">
              <li>Ingresa a <code className="text-amber-400">make.powerautomate.com</code> con tu correo UD.</li>
              <li>Crea un Flujo Automatizado: <em>"Cuando llega un nuevo correo electrónico (V3)"</em>.</li>
              <li>Filtra por remitente: <code className="text-amber-400">@udistrital.edu.co</code>.</li>
              <li>Agrega una acción HTTP POST hacia tu webhook: <code className="text-amber-400">/api/v1/webhooks/incoming-email</code>.</li>
              <li>Pasa el encabezado <code className="text-amber-400">X-Webhook-Secret</code> con tu clave secreta de <code className="text-zinc-300">.env</code>.</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminSimulatorPage;

