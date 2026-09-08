import re
import os
from typing import Dict, Any, List, Optional
from pypdf import PdfReader

class MarkdownConverter:
    """
    Converts regulatory academic PDF documents (Resoluciones, Acuerdos UD)
    into structured clean Markdown, formatting titles, chapters, and articles,
    and detecting conflict / derogation clauses.
    """

    DEROGATION_PATTERNS = [
        r"(?:deroga|derógase|deja sin efecto|sustituye|abroga)\s+(?:a\s+)?(?:la\s+)?(?:resolución|acuerdo|circular|norma)?\s*([0-9]{1,4}(?:\s+de\s+[0-9]{4})?)",
        r"(?:modifica|modifícase)\s+(?:el\s+art[íi]culo\s+[0-9]+[oº]?\s+de(?:l)?\s+)?(?:la\s+)?(?:resolución|acuerdo)\s*([0-9]{1,4}(?:\s+de\s+[0-9]{4})?)",
    ]

    def convert_pdf_to_markdown(self, pdf_path: str, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Reads a PDF, cleans OCR/formatting noise, organizes sections into Markdown,
        and extracts potential supersession/derogation links.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF no encontrado en: {pdf_path}")

        reader = PdfReader(pdf_path)
        raw_pages: List[str] = []

        for idx, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
                cleaned = self._clean_page_text(text, idx + 1)
                if cleaned:
                    raw_pages.append(cleaned)
            except Exception as e:
                print(f"[MarkdownConverter] Error extrayendo página {idx + 1}: {e}")

        full_text = "\n\n".join(raw_pages)
        markdown_body = self._format_as_markdown(full_text, title)
        detected_derogations = self._detect_derogations(full_text)

        return {
            "markdown": markdown_body,
            "page_count": len(reader.pages),
            "detected_derogations": detected_derogations,
            "has_conflict_clause": len(detected_derogations) > 0,
        }

    def _clean_page_text(self, text: str, page_num: int) -> str:
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue
            if re.match(r"^P[aá]gina\s+\d+(\s+de\s+\d+)?$", trimmed, re.IGNORECASE):
                continue
            if re.match(r"^\d+\s*$", trimmed):
                continue
            if "UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS" in trimmed.upper():
                continue
            cleaned_lines.append(trimmed)

        return "\n".join(cleaned_lines)

    def _format_as_markdown(self, text: str, fallback_title: Optional[str] = None) -> str:
        lines = text.split("\n")
        formatted: List[str] = []
        has_main_heading = False

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            # Detect main document resolution / agreement
            if re.match(r"^(ACUERDO|RESOLUCI[ÓO]N|CIRCULAR)\s+(No\.\s*|NÚMERO\s*)?[0-9]+", line_clean, re.IGNORECASE):
                formatted.append(f"\n# {line_clean}\n")
                has_main_heading = True
                continue

            # Detect chapters / titles
            if re.match(r"^(CAP[IÍ]TULO|T[IÍ]TULO)\s+[IVXLCDM0-9]+", line_clean, re.IGNORECASE):
                formatted.append(f"\n## {line_clean}\n")
                continue

            # Detect articles
            if re.match(r"^(ART[IÍ]CULO|PAR[AÁ]GRAFO)\s+[0-9]+[oº\.]?", line_clean, re.IGNORECASE):
                formatted.append(f"\n### {line_clean}\n")
                continue

            # Detect bullet points / numbered items
            if re.match(r"^[0-9]+[\.\)]\s+", line_clean):
                formatted.append(f"{line_clean}")
                continue
            if re.match(r"^[a-z][\.\)]\s+", line_clean):
                formatted.append(f"  - {line_clean}")
                continue

            formatted.append(line_clean)

        result = "\n\n".join(formatted)
        if not has_main_heading and fallback_title:
            result = f"# {fallback_title}\n\n{result}"

        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def _detect_derogations(self, text: str) -> List[str]:
        found: List[str] = []
        for pattern in self.DEROGATION_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for m in matches:
                ref = m.group(1).strip()
                if ref and ref not in found:
                    found.append(ref)
        return found

markdown_converter = MarkdownConverter()

