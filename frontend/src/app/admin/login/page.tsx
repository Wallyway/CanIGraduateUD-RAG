"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { GraduationCap, Lock, User, AlertCircle, Loader2 } from "lucide-react";
import { loginAdmin } from "@/lib/api";
import { setAdminToken } from "@/lib/storage";

export default function AdminLoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const data = await loginAdmin(username, password);
      if (data.access_token) {
        setAdminToken(data.access_token);
        router.push("/admin");
      } else {
        setError("Respuesta de autenticación no válida.");
      }
    } catch (err: any) {
      setError(err.message || "Credenciales incorrectas.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-zinc-950">
      <div className="w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-2xl p-8 shadow-2xl space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-red-900 border border-red-700/60 mx-auto flex items-center justify-center text-amber-400 shadow-md">
            <GraduationCap className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-zinc-100 tracking-tight">
            Acceso Administrativo
          </h1>
          <p className="text-xs text-zinc-400">
            Gestión y Triage de Comunicados • Universidad Distrital
          </p>
        </div>

        {error && (
          <div className="bg-red-950/50 border border-red-800/60 rounded-xl p-3 flex items-start gap-2.5 text-xs text-red-300">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Usuario Administrador
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Ingresa tu usuario"
                className="w-full bg-zinc-950 border border-zinc-800 focus:border-red-600 focus:ring-1 focus:ring-red-600 rounded-xl py-2.5 pl-10 pr-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Contraseña
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full bg-zinc-950 border border-zinc-800 focus:border-red-600 focus:ring-1 focus:ring-red-600 rounded-xl py-2.5 pl-10 pr-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition"
              />
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 px-4 bg-red-800 hover:bg-red-700 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition flex items-center justify-center gap-2 shadow-sm cursor-pointer"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                "Ingresar al Panel"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

