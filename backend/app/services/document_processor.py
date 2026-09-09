import re
import os
import logging
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader

logger = logging.getLogger(__name__)

class DocumentProcessor:
    @staticmethod
    def is_pairwise_duplicated(token: str) -> bool:
        """Checks if all characters in the token are repeated in adjacent pairs."""
        if len(token) < 2 or len(token) % 2 != 0:
            return False
        return all(token[i] == token[i+1] for i in range(0, len(token), 2))

    def clean_shadow_duplicates(self, text: str) -> str:
        """
        Detects and removes drop-shadow / faux-bold vector glyph duplication artifacts
        (e.g., 'UUNNIIVVEERRSSIIDDAADD' -> 'UNIVERSIDAD') commonly produced by official
        Colombian university PDF generators that print grey shadow glyphs under black text.

        Preserves standard Spanish double letters ('rr', 'll', 'cc', 'ee', 'oo'),
        roman numerals ('I', 'II', 'III'), and non-duplicated paragraphs.
        """
        if not text:
            return ""

        paragraphs = text.split("\n\n")
        cleaned_paragraphs = []

        for para in paragraphs:
            tokens = para.split()
            if not tokens:
                cleaned_paragraphs.append(para)
                continue

            # Check if paragraph contains long pairwise duplicated words (length >= 4)
            dup_evidence_count = sum(1 for t in tokens if len(t) >= 4 and self.is_pairwise_duplicated(t))
            is_shadow_para = (dup_evidence_count >= 1)

            if not is_shadow_para:
                cleaned_paragraphs.append(para)
                continue

            lines = para.split("\n")
            cleaned_lines = []
            for line in lines:
                line_tokens = re.split(r'(\s+)', line)
                line_has_dup = any(len(t) >= 4 and self.is_pairwise_duplicated(t) for t in line_tokens if t.strip())

                cleaned_toks = []
                for tok in line_tokens:
                    if not tok.strip():
                        cleaned_toks.append(tok)
                    elif len(tok) >= 4 and self.is_pairwise_duplicated(tok):
                        cleaned_toks.append(tok[::2])
                    elif (line_has_dup or is_shadow_para) and len(tok) == 2 and tok[0] == tok[1]:
                        # Short 2-char token like 'yy', 'aa', '""', '00', '..' in duplicated context
                        cleaned_toks.append(tok[0])
                    elif (line_has_dup or is_shadow_para) and re.search(r'(.)\1(.)\2', tok):
                        # Mixed token with run of doubles (e.g. attached punctuation)
                        cleaned_toks.append(re.sub(r'(.)\1', r'\1', tok))
                    else:
                        cleaned_toks.append(tok)
                cleaned_lines.append("".join(cleaned_toks))
            cleaned_paragraphs.append("\n".join(cleaned_lines))

        return "\n\n".join(cleaned_paragraphs)

    def extract_text_from_file(self, file_path: str) -> str:
        """Extracts plain text from PDF or Markdown/Text files."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return self._extract_text_from_pdf(file_path)
        else:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                return self.clean_shadow_duplicates(content)

    def _extract_text_from_pdf(self, file_path: str) -> str:
        text_parts = []
        try:
            reader = PdfReader(file_path)
            for i, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text(extraction_mode="layout") or ""
                except Exception:
                    page_text = page.extract_text() or ""
                clean_text = self.clean_shadow_duplicates(page_text)

                lines = clean_text.split('\n')
                if i > 0:
                    filtered_lines = []
                    in_running_header = True
                    for line_idx, line in enumerate(lines):
                        stripped = line.strip()
                        if in_running_header and line_idx < 15:
                            if any(kw in stripped.upper() for kw in [
                                'UNIVERSIDAD DISTRITAL',
                                'FRANCISCO JOSÉ DE CALDAS',
                                'CONSEJO ACADEMICO',
                                'CONSEJO ACADÉMICO',
                                'CONSEJO SUPERIOR',
                                'ACUERDO N°',
                                'ACUERDO NO',
                                'ACUERDO NUMERO',
                                'RESOLUCIÓN N°',
                                'RESOLUCION N°',
                            ]) or (stripped.startswith('"Por ') or stripped.startswith('“Por ') or stripped.endswith('Caldas"') or stripped.endswith('Caldas”')) or re.match(r'^\([A-Za-z]+\s+\d+\s+de\s+\d+\)$', stripped) or re.match(r'^[A-Z0-9\^\{\}\*]{1,6}$', stripped):
                                continue
                            elif not stripped:
                                continue
                            else:
                                in_running_header = False

                        if re.search(r'P[áa]gina\s+\d+\s+de(?:\s+\d+)?', stripped, re.IGNORECASE):
                            continue

                        filtered_lines.append(re.sub(r'[ \t]{2,}', ' ', stripped))
                    clean_text = '\n'.join(filtered_lines)
                else:
                    lines = [re.sub(r'[ \t]{2,}', ' ', l).strip() for l in lines if not re.search(r'P[áa]gina\s+\d+\s+de(?:\s+\d+)?', l, re.IGNORECASE)]
                    clean_text = '\n'.join(lines)

                text_parts.append(f"\n--- [Página {i+1}] ---\n{clean_text}")
        except Exception as e:
            logger.error(f"Error reading PDF {file_path}: {e}")
            raise e
        return "\n".join(text_parts)

    def extract_official_metadata(self, text: str) -> Dict[str, str]:
        """
        Extracts official agreement / resolution title, number, entity, and date
        from university regulatory text.
        """
        main_norm = re.search(
            r'(ACUERDO|RESOLUCI[OÓ]N|CIRCULAR)\s*(?:N[°o]\.?|No\.?)?\s*(\d+)[\s\n]*\(([A-Za-z]+)\s+(\d{1,2})\s+de\s+(\d{4})\)',
            text,
            re.IGNORECASE
        )
        body_match = re.search(
            r'(CONSEJO\s+(?:ACAD[EÉ]MICO|SUPERIOR(?:\s+UNIVERSITARIO)?))',
            text,
            re.IGNORECASE
        )
        body_str = body_match.group(1).title() if body_match else ''

        months = {
            'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
            'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
        }

        if main_norm:
            norm_type, num_str, m_name, day, yr = main_norm.groups()
            doc_num = int(num_str)
            m_num = months.get(m_name.lower(), '01')
            iso_date = f'{yr}-{m_num}-{int(day):02d}'
            res_num = f'{norm_type.title()} {doc_num:03d} de {yr}'
        else:
            res_match = re.search(r'(ACUERDO|RESOLUCI[OÓ]N|CIRCULAR)\s*(?:N[°o]\.?|No\.?)?\s*(\d+)', text, re.IGNORECASE)
            date_match = re.search(r'\(([A-Za-z]+)\s+(\d{1,2})\s+de\s+(\d{4})\)', text)
            if res_match and date_match:
                m_name, day, yr = date_match.groups()
                m_num = months.get(m_name.lower(), '01')
                iso_date = f'{yr}-{m_num}-{int(day):02d}'
                res_num = f'{res_match.group(1).title()} {int(res_match.group(2)):03d} de {yr}'
            elif res_match:
                res_num = f'{res_match.group(1).title()} {int(res_match.group(2)):03d}'
                iso_date = ''
            else:
                res_num = ''
                iso_date = ''

        if body_str and res_num:
            res_num += f' - {body_str}'

        title_match = re.search(r'[\"“](Por (?:el|la) cual[^\n\"”]+(?:\n[^\n\"”]+)*)[\"”]', text, re.IGNORECASE)
        purpose = re.sub(r'\s+', ' ', title_match.group(1)).strip() if title_match else ''
        clean_title = res_num or 'Resolución Oficial'
        if purpose:
            if len(purpose) > 130:
                clean_title += f': {purpose[:127]}...'
            else:
                clean_title += f': {purpose}'

        return {
            'resolution_number': res_num,
            'title': clean_title,
            'effective_date': iso_date
        }

    def chunk_normative_text(
        self,
        text: str,
        doc_metadata: Dict[str, Any],
        max_chunk_size: int = 1800,
        overlap: int = 200
    ) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
        """
        Structure-aware chunker that respects Articles, Chapters, and Headings
        to preserve official legal / normative context for RAG.
        """
        chunks: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        chunk_ids: List[str] = []

        # Split text by Articles or major section headers if present
        pattern = r'(?=(?:###?\s*(?:Artículo|Articulo|CAPÍTULO|TITULO|Etapa|\d+\.))|(?:Artículo\s+\d+))'
        raw_sections = re.split(pattern, text, flags=re.IGNORECASE)

        doc_id = doc_metadata.get("document_id", 0)
        doc_title = doc_metadata.get("title", "Documento Oficial")
        res_number = doc_metadata.get("resolution_number", "")

        section_counter = 0
        for section in raw_sections:
            clean_sec = section.strip()
            if not clean_sec or len(clean_sec) < 30:
                continue

            # Identify if this section starts with an Article or header
            first_line = clean_sec.split("\n")[0].strip()
            current_article = first_line[:100] if any(kw in first_line.lower() for kw in ["artículo", "articulo", "capítulo", "requisito", "etapa"]) else "Disposiciones Generales"

            # If section fits in max_chunk_size
            if len(clean_sec) <= max_chunk_size:
                section_counter += 1
                chunk_id = f"doc_{doc_id}_sec_{section_counter}"
                chunk_text = f"[{doc_title} - {res_number}]\nSección: {current_article}\n\n{clean_sec}"
                
                chunks.append(chunk_text)
                chunk_meta = dict(doc_metadata)
                chunk_meta["article"] = current_article
                chunk_meta["chunk_id"] = chunk_id
                metadatas.append(chunk_meta)
                chunk_ids.append(chunk_id)
            else:
                # Sub-chunk large articles by paragraph
                paragraphs = clean_sec.split("\n\n")
                current_sub = []
                current_len = 0
                sub_index = 0

                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    if current_len + len(para) > max_chunk_size and current_sub:
                        section_counter += 1
                        sub_index += 1
                        sub_text = "\n\n".join(current_sub)
                        chunk_id = f"doc_{doc_id}_sec_{section_counter}_{sub_index}"
                        full_chunk = f"[{doc_title} - {res_number}]\nSección: {current_article} (Parte {sub_index})\n\n{sub_text}"
                        
                        chunks.append(full_chunk)
                        chunk_meta = dict(doc_metadata)
                        chunk_meta["article"] = current_article
                        chunk_meta["chunk_id"] = chunk_id
                        metadatas.append(chunk_meta)
                        chunk_ids.append(chunk_id)

                        current_sub = [para]
                        current_len = len(para)
                    else:
                        current_sub.append(para)
                        current_len += len(para)

                if current_sub:
                    section_counter += 1
                    sub_index += 1
                    sub_text = "\n\n".join(current_sub)
                    chunk_id = f"doc_{doc_id}_sec_{section_counter}_{sub_index}"
                    full_chunk = f"[{doc_title} - {res_number}]\nSección: {current_article} (Parte {sub_index})\n\n{sub_text}"
                    
                    chunks.append(full_chunk)
                    chunk_meta = dict(doc_metadata)
                    chunk_meta["article"] = current_article
                    chunk_meta["chunk_id"] = chunk_id
                    metadatas.append(chunk_meta)
                    chunk_ids.append(chunk_id)

        return chunks, metadatas, chunk_ids

document_processor = DocumentProcessor()

