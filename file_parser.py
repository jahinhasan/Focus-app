import os
import mimetypes

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import docx
except ImportError:
    docx = None

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

class FileParser:
    def __init__(self):
        self.ocr_available = False
        # Check for tesseract binary strictly if needed, but for now just check import
        if pytesseract:
            try:
                # Simple check if tesseract is actually executable
                # This might still fail if not in PATH, handled at runtime
                self.ocr_available = True
            except:
                pass

    def extract_text(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        _, ext = os.path.splitext(file_path.lower())

        if ext == '.pdf':
            return self._parse_pdf(file_path)
        elif ext in ['.docx', '.doc']:
            return self._parse_docx(file_path)
        elif ext in ['.png', '.jpg', '.jpeg', '.bmp']:
            return self._parse_image(file_path)
        elif ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _parse_pdf(self, path):
        if not PyPDF2:
            raise ImportError("PyPDF2 not installed")
        
        text = []
        try:
            with open(path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text.append(page.extract_text())
        except Exception as e:
            return f"Error reading PDF: {e}"
            
        return "\n".join(text)

    def _parse_docx(self, path):
        if not docx:
            raise ImportError("python-docx not installed")
        
        try:
            doc = docx.Document(path)
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            return f"Error reading DOCX: {e}"

    def _parse_image(self, path):
        if not self.ocr_available or not Image:
            return "[Error: OCR tools (tesseract/Pillow) not available. Text cannot be extracted from images.]"
        
        try:
            return pytesseract.image_to_string(Image.open(path))
        except Exception as e:
            return f"Error performing OCR: {e} (Tesseract might not be installed on system)"
