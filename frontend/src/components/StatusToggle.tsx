"use client";

import React, { useState } from "react";
import { Bot, UserCheck, Loader2 } from "lucide-react";
import { toggleAutonomousMode } from "@/lib/api";

interface StatusToggleProps {
  initialStatus: boolean;
  onToggle?: (newStatus: boolean) => void;
}

export const StatusToggle: React.FC<StatusToggleProps> = ({
  initialStatus,
  onToggle,
}) => {
  const [enabled, setEnabled] = useState(initialStatus);
  const [isUpdating, setIsUpdating] = useState(false);

  const handleSwitch = async () => {
    const nextState = !enabled;
    setIsUpdating(true);
    try {
      await toggleAutonomousMode(nextState);
      setEnabled(nextState);
      onToggle?.(nextState);
    } catch (e) {
      console.error("Error updating autonomous mode", e);
      alert("Error al actualizar la configuración del modo autónomo.");
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
      <div className="flex items-start sm:items-center gap-3">
        <div
          className={`w-10 h-10 rounded-xl flex items-center justify-center transition ${
            enabled
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
              : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
          }`}
        >
          {enabled ? <Bot className="w-5 h-5" /> : <UserCheck className="w-5 h-5" />}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-sm text-zinc-100">
              {enabled ? "Modo Agéntico Autónomo" : "Supervisión Humana (Human-in-the-loop)"}
            </h3>
            <span
              className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${
                enabled
                  ? "bg-emerald-950/60 text-emerald-300 border-emerald-700/50"
                  : "bg-amber-950/60 text-amber-300 border-amber-700/50"
              }`}
            >
              {enabled ? "Activo" : "Revisión Manual"}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 max-w-xl">
            {enabled
              ? "Los comunicados relevantes recibidos por correo se indexan directamente en la base de conocimiento vectorial sin requerir aprobación manual previa."
              : "Los correos entrantes son analizados por el LLM y quedan en estado 'Pendiente de Revisión' para que tú decidas si se aprueban o descartan."}
          </p>
        </div>
      </div>

      <button
        onClick={handleSwitch}
        disabled={isUpdating}
        className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition shadow-sm ${
          enabled
            ? "bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700"
            : "bg-emerald-600 hover:bg-emerald-500 text-white"
        }`}
      >
        {isUpdating ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : enabled ? (
          "Cambiar a Supervisado"
        ) : (
          "Activar Modo Autónomo"
        )}
      </button>
    </div>
  );
};

