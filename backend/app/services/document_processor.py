import re
import os
import logging
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def extract_text_from_file(self, file_path: str) -> str:
        """Extracts plain text from PDF or Markdown/Text files."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return self._extract_text_from_pdf(file_path)
        else:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

    def _extract_text_from_pdf(self, file_path: str) -> str:
        text_parts = []
        try:
            reader = PdfReader(file_path)
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                text_parts.append(f"\n--- [Página {i+1}] ---\n{page_text}")
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

