try:
    import pymupdf as fitz
except ImportError:
    import fitz

from typing import Dict, List, Any

class PDFExtractionError(Exception):
    pass

class PDFExtractor:
    MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB

    @staticmethod
    def validate_file(file_obj) -> None:
        if not file_obj.name.lower().endswith('.pdf'):
            raise PDFExtractionError("Only PDF files (.pdf) are supported.")
        if file_obj.size > PDFExtractor.MAX_FILE_SIZE_BYTES:
            raise PDFExtractionError(f"File size exceeds the 15 MB limit (Current: {file_obj.size / (1024*1024):.2f} MB).")

    @staticmethod
    def extract_text_and_chunks(file_path_or_stream) -> Dict[str, Any]:
        """
        Extracts readable text page by page using PyMuPDF.
        Detects if scanned / no extractable text (requiring OCR).
        Returns total_pages, full_text, chunks by page/section.
        """
        try:
            doc = fitz.open(file_path_or_stream)
        except Exception as e:
            raise PDFExtractionError(f"Failed to open PDF document: {str(e)}")

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            raise PDFExtractionError("The uploaded PDF has 0 pages.")

        pages_data: List[Dict[str, Any]] = []
        total_extracted_chars = 0

        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_text = page.get_text("text").strip()
            char_count = len(page_text)
            total_extracted_chars += char_count

            if char_count > 0:
                pages_data.append({
                    'page_number': page_idx + 1,
                    'text': page_text,
                    'char_count': char_count
                })

        doc.close()

        # Check if empty or scanned (average less than 25 characters per page)
        if total_extracted_chars < 50:
            return {
                'total_pages': total_pages,
                'full_text': '',
                'pages': [],
                'is_ocr_required': True,
                'message': "This document appears to be scanned or contains no extractable text. Optical Character Recognition (OCR) is required."
            }

        full_text = "\n\n".join([f"--- Page {p['page_number']} ---\n{p['text']}" for p in pages_data])

        # Create structured chunks for question generation
        chunks = []
        for p in pages_data:
            chunks.append({
                'source': f"Page {p['page_number']}",
                'content': p['text']
            })

        return {
            'total_pages': total_pages,
            'full_text': full_text,
            'pages': pages_data,
            'chunks': chunks,
            'is_ocr_required': False,
            'message': f"Successfully extracted {total_extracted_chars} characters across {len(pages_data)} readable pages."
        }
