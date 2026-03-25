import sys
import importlib.util

def check_install(package):
    spec = importlib.util.find_spec(package)
    return spec is not None

def extract_text(pdf_path):
    # Try pypdf first
    if check_install("pypdf"):
        from pypdf import PdfReader
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            print("--- pypdf extraction ---")
            print(text)
            return
        except Exception as e:
            print(f"pypdf failed: {e}")

    # Try PyPDF2
    if check_install("PyPDF2"):
        import PyPDF2
        try:
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            print("--- PyPDF2 extraction ---")
            print(text)
            return
        except Exception as e:
            print(f"PyPDF2 failed: {e}")
            
    # Fallback to PDFMiner
    if check_install("pdfminer"):
        try:
            from pdfminer.high_level import extract_text
            text = extract_text(pdf_path)
            print("--- pdfminer extraction ---")
            print(text)
            return
        except Exception as e:
             print(f"pdfminer failed: {e}")

    print("No suitable PDF library found (pypdf, PyPDF2, pdfminer).")

if __name__ == "__main__":
    extract_text("/Users/linkb/PycharmProjects/my_app/test_platform/活动小程序V1.0.pdf")
