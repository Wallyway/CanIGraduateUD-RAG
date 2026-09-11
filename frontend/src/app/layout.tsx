import type { Metadata, Viewport } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://www.canigraduateud.site";

export const viewport: Viewport = {
  themeColor: "#09090b",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "CanIGraduateUD - Asistente Académico RAG | Universidad Distrital",
    template: "%s | CanIGraduateUD",
  },
  description:
    "Asistente académico RAG oficial con citas normativas verificadas para estudiantes de la Universidad Distrital Francisco José de Caldas y Facultad de Ingeniería. Consulta opciones de grado, pasantía, monografía, coterminal, materias de posgrado, requisitos de créditos, paz y salvos y suficiencia de inglés B2.",
  applicationName: "CanIGraduateUD - Asistente Académico RAG",
  keywords: [
    "Universidad Distrital Francisco José de Caldas",
    "Facultad de Ingeniería",
    "opciones de grado",
    "pasantía",
    "monografía",
    "coterminal",
    "posgrados",
    "normativas",
    "acuerdos",
    "Ingeniería de Sistemas",
    "modalidades de grado",
    "materias de posgrado",
    "créditos académicos",
    "paz y salvos UD",
    "inglés B2 ILUD",
    "Acuerdo 038 de 2015",
    "Acuerdo 027 de 1993",
    "Resolución 004 de 2021",
    "Consejo de Facultad",
    "trabajo de grado",
    "asistente académico RAG",
    "inteligencia artificial educativa",
    "RAG Universidad Distrital",
  ],
  authors: [
    {
      name: "Comunidad de Ingeniería de Sistemas - Universidad Distrital Francisco José de Caldas",
      url: "https://www.udistrital.edu.co",
    },
  ],
  creator: "Universidad Distrital Francisco José de Caldas",
  publisher: "Facultad de Ingeniería - Universidad Distrital Francisco José de Caldas",
  category: "Education",
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  alternates: {
    canonical: siteUrl,
    languages: {
      "es-CO": siteUrl,
      "es": siteUrl,
    },
  },
  openGraph: {
    type: "website",
    locale: "es_CO",
    url: siteUrl,
    siteName: "CanIGraduateUD - Asistente Académico RAG",
    title: "CanIGraduateUD - Asistente Académico RAG | Opciones y Normativas de Grado UD",
    description:
      "Asistente académico inteligente RAG con citas normativas oficiales para orientación en opciones de grado, pasantías, monografías, coterminal, posgrados y requisitos en la Facultad de Ingeniería de la Universidad Distrital Francisco José de Caldas.",
    images: [
      {
        url: "/images/logo-canigraduateud-white.png",
        width: 1775,
        height: 417,
        alt: "CanIGraduateUD - Asistente Académico RAG - Universidad Distrital Francisco José de Caldas",
        type: "image/png",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "CanIGraduateUD - Asistente Académico RAG | Grados e Ingeniería UD",
    description:
      "Consulta normativa inmediata con citas oficiales para opciones de grado, pasantía, monografía, coterminal y posgrados en la Universidad Distrital.",
    images: ["/images/logo-canigraduateud-white.png"],
    creator: "@udistrital",
    site: "@udistrital",
  },
  robots: {
    index: true,
    follow: true,
    nocache: false,
    googleBot: {
      index: true,
      follow: true,
      noimageindex: false,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
    ],
    shortcut: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
};

const jsonLdData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": ["SoftwareApplication", "EducationalApplication"],
      "@id": `${siteUrl}/#app`,
      name: "CanIGraduateUD - Asistente Académico RAG",
      alternateName: ["Can I Graduate UD?", "CanIGraduateUD"],
      url: siteUrl,
      applicationCategory: "EducationalApplication",
      operatingSystem: "Web",
      inLanguage: "es-CO",
      description:
        "Asistente académico inteligente RAG con citas normativas oficiales para la orientación de opciones y requisitos de grado en la Facultad de Ingeniería de la Universidad Distrital Francisco José de Caldas.",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "COP",
      },
      featureList: [
        "Consulta normativa con citas textuales y resoluciones oficiales",
        "Orientación en modalidades y opciones de grado (pasantía, monografía, coterminal, posgrados)",
        "Verificación de porcentajes y créditos académicos requeridos",
        "Guía de suficiencia y acreditación de inglés nivel B2 (ILUD)",
        "Trámite paso a paso de paz y salvos institucionales",
        "Búsqueda semántica sobre acuerdos (Acuerdo 038 de 2015, Acuerdo 027 de 1993)",
      ],
      author: {
        "@id": "https://www.udistrital.edu.co/#organization",
      },
      publisher: {
        "@id": "https://www.udistrital.edu.co/#organization",
      },
    },
    {
      "@type": "CollegeOrUniversity",
      "@id": "https://www.udistrital.edu.co/#organization",
      name: "Universidad Distrital Francisco José de Caldas",
      alternateName: "Universidad Distrital",
      url: "https://www.udistrital.edu.co",
      logo: `${siteUrl}/images/logo-ud.png`,
      department: {
        "@type": "EducationalOrganization",
        name: "Facultad de Ingeniería",
        url: "https://ingenieria.udistrital.edu.co",
        department: {
          "@type": "EducationalOrganization",
          name: "Proyecto Curricular de Ingeniería de Sistemas",
        },
      },
      address: {
        "@type": "PostalAddress",
        streetAddress: "Carrera 7 No. 40B - 53",
        addressLocality: "Bogotá",
        addressRegion: "Bogotá D.C.",
        addressCountry: "CO",
      },
    },
    {
      "@type": "WebSite",
      "@id": `${siteUrl}/#website`,
      url: siteUrl,
      name: "CanIGraduateUD - Asistente Académico RAG",
      description:
        "Portal de orientación normativa y académica para opciones de grado en la Universidad Distrital Francisco José de Caldas.",
      inLanguage: "es-CO",
      publisher: {
        "@id": "https://www.udistrital.edu.co/#organization",
      },
    },
    {
      "@type": "FAQPage",
      "@id": `${siteUrl}/#faq`,
      mainEntity: [
        {
          "@type": "Question",
          name: "¿Cuáles son las modalidades u opciones de grado en Ingeniería de Sistemas UD?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "Según el Acuerdo 038 de 2015 del Consejo Superior Universitario, las modalidades de grado incluyen: Pasantía institucional, Monografía, Materias de Posgrado (coterminal en especialización o maestría), Creación de Empresa, Producción Técnica o Tecnológica y Semillero de Investigación.",
          },
        },
        {
          "@type": "Question",
          name: "¿Cuántos créditos se requieren para postular a una pasantía como opción de grado?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "El estudiante debe haber cursado y aprobado como mínimo el setenta por ciento (70%) del total de créditos académicos de su plan de estudios y encontrarse a paz y salvo académica y disciplinariamente.",
          },
        },
        {
          "@type": "Question",
          name: "¿Cómo funciona la modalidad coterminal o materias de posgrado?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "Bajo el Acuerdo 038 de 2015, los estudiantes con al menos el 80% de créditos aprobados y un promedio acumulado igual o superior a 3.8 pueden cursar asignaturas de primer semestre de un posgrado propio de la Universidad Distrital como modalidad de grado.",
          },
        },
        {
          "@type": "Question",
          name: "¿Cómo se acredita el requisito de lengua extranjera inglés B2 en la Universidad Distrital?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "Conforme a la Resolución 004 de 2021 del Consejo Académico, se acredita aprobando los niveles correspondientes en el Instituto de Lenguas de la Universidad Distrital (ILUD), aprobando el examen de suficiencia institucional, o mediante convalidación de pruebas estandarizadas internacionales vigentes (TOEFL, IELTS, MET, Cambridge B2 First).",
          },
        },
        {
          "@type": "Question",
          name: "¿Qué paz y salvos y documentos se requieren para radicar la carpeta de grado?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "Se requiere paz y salvo de la Biblioteca Central, paz y salvo de Bienestar Institucional, paz y salvo de laboratorios y salas especializadas, entrega de carnet estudiantil o constancia respectiva, y el comprobante de pago de derechos pecuniarios de grado.",
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
    <html lang="es-CO" className="dark h-full">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdData) }}
        />
      </head>
      <body className="min-h-[100dvh] bg-zinc-950 font-sans text-zinc-100 flex flex-col overscroll-none">
        {children}
        <Analytics />
      </body>
    </html>
  );
}


