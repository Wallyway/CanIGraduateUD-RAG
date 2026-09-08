import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Can I Graduate UD? | Asistente de Grados - Ingeniería de Sistemas",
  description: "Sistema RAG oficial para resolver dudas sobre requisitos, modalidades y trámites de grado de Ingeniería de Sistemas de la Universidad Distrital Francisco José de Caldas.",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark">
      <body className="min-h-screen bg-zinc-950 font-sans text-zinc-100 flex flex-col">
        {children}
      </body>
    </html>
  );
}

