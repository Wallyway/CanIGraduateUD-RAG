import type { Metadata } from "next";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://canigraduateud.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Can I Graduate UD? | Asistente de Grados - Ingeniería de Sistemas UD",
    template: "%s | Can I Graduate UD?",
  },
  description:
    "Sistema RAG oficial con citas normativas verificadas para resolver dudas sobre requisitos, modalidades de grado, pasantías, materias de posgrado, paz y salvos y acreditación de inglés B2 en Ingeniería de Sistemas de la Universidad Distrital Francisco José de Caldas.",
  keywords: [
    "Universidad Distrital",
    "Ingeniería de Sistemas",
    "Grados UD",
    "Modalidades de Grado",
    "Pasantías UD",
    "Monografía UD",
    "Acuerdo 038 de 2015",
    "Acuerdo 027 de 1993",
    "Paz y Salvos UD",
    "Inglés B2 ILUD",
    "RAG Universidad Distrital",
    "Francisco José de Caldas",
    "Facultad de Ingeniería UD",
  ],
  authors: [{ name: "Comunidad Ingeniería de Sistemas - Universidad Distrital" }],
  creator: "Universidad Distrital Francisco José de Caldas",
  publisher: "Facultad de Ingeniería - Universidad Distrital",
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  alternates: {
    canonical: siteUrl,
  },
  openGraph: {
    type: "website",
    locale: "es_CO",
    url: siteUrl,
    title: "Can I Graduate UD? | Asistente Oficial de Grados - Ingeniería de Sistemas",
    description:
      "Consulta inmediata sustentada en acuerdos y resoluciones oficiales para estudiantes de Ingeniería de Sistemas de la Universidad Distrital.",
    siteName: "Can I Graduate UD?",
  },
  twitter: {
    card: "summary_large_image",
    title: "Can I Graduate UD? | Asistente Oficial de Grados UD",
    description:
      "Guía oficial sustentada en acuerdos y resoluciones para graduarse en Ingeniería de Sistemas - Universidad Distrital.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  icons: {
    icon: "/favicon.ico",
  },
};

const jsonLdData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebApplication",
      "@id": `${siteUrl}/#app`,
      "name": "Can I Graduate UD?",
      "url": siteUrl,
      "applicationCategory": "EducationalApplication",
      "operatingSystem": "All",
      "inLanguage": "es",
      "description":
        "Asistente inteligente RAG oficial de grados para estudiantes de Ingeniería de Sistemas de la Universidad Distrital Francisco José de Caldas.",
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "COP",
      },
    },
    {
      "@type": "EducationalOrganization",
      "@id": "https://www.udistrital.edu.co/#organization",
      "name": "Universidad Distrital Francisco José de Caldas",
      "url": "https://www.udistrital.edu.co",
      "department": {
        "@type": "Organization",
        "name": "Proyecto Curricular de Ingeniería de Sistemas - Facultad de Ingeniería",
      },
    },
    {
      "@type": "FAQPage",
      "@id": `${siteUrl}/#faq`,
      "mainEntity": [
        {
          "@type": "Question",
          "name": "¿Cuáles son las modalidades de grado en Ingeniería de Sistemas UD?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text":
              "Según el Acuerdo 038 de 2015, las modalidades incluyen: Pasantía institucional, Monografía, Materias de Posgrado (especialización o maestría), Creación de Empresa, Producción Técnica o Tecnológica y Semillero de Investigación.",
          },
        },
        {
          "@type": "Question",
          "name": "¿Cuántos créditos necesito para postular una pasantía de grado?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text":
              "El estudiante debe tener aprobado como mínimo el 70% del total de créditos académicos de su plan de estudios y no encontrarse bajo sanción disciplinaria.",
          },
        },
        {
          "@type": "Question",
          "name": "¿Cómo se acredita el requisito de inglés B2 en la Universidad Distrital?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text":
              "Conforme a la Resolución 004 de 2021, aprobando los cursos regulares del ILUD hasta nivel B2, presentando examen de suficiencia ante el ILUD o mediante homologación de exámenes internacionales vigentes (TOEFL, IELTS, MET, Cambridge).",
          },
        },
        {
          "@type": "Question",
          "name": "¿Qué paz y salvos se requieren para radicar la carpeta de grado?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text":
              "Paz y salvo de Biblioteca Central, Bienestar Institucional, laboratorios/salas de sistemas, devolución o constancia de carnet estudiantil y comprobante de pago de derechos de grado.",
          },
        },
      ],
    },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdData) }}
        />
      </head>
      <body className="min-h-screen bg-zinc-950 font-sans text-zinc-100 flex flex-col">
        {children}
      </body>
    </html>
  );
}


