from reportlab.pdfgen import canvas

def create_dummy_pdf(filename):
    c = canvas.Canvas(filename)
    c.drawString(100, 750, "Hello World from Requirement Review Agent!")
    c.drawString(100, 730, "This is a dummy PDF for testing vision capabilities.")
    c.save()

if __name__ == "__main__":
    create_dummy_pdf("test_platform/tools/test.pdf")
    print("Created test_platform/tools/test.pdf")
