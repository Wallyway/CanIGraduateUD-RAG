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
                page_text = page.extract_text() or ""
                clean_text = self.clean_shadow_duplicates(page_text)
                text_parts.append(f"\n--- [Página {i+1}] ---\n{clean_text}")
        except Exception as e:
            logger.error(f"Error reading PDF {file_path}: {e}")
            raise e
        return "\n".join(text_parts)

    def chunk_normative_text(
        self,
        text: str,
        doc_metadata: Dict[str, Any],
        max_chunk_size: int = 1200,
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

