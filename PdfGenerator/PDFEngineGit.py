import os
import sys
import pdfkit
import base64
import PyPDF2
import shutil
from github import Github
import json
import qrcode
import uuid
import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLineEdit, 
                             QPushButton, QLabel, QMessageBox, QFileDialog)

if sys.platform == "win32":
    PATH_TO_WKHTMLTOPDF = r'./wkhtmltopdf/bin/wkhtmltopdf.exe'
elif sys.platform == "linux" or "linux2":
    PATH_TO_WKHTMLTOPDF = r'./wkhtmltopdf/wkhtmltopdf'
elif sys.platform == "darwin" or "os2" or "os2emx":
    print("mcos")

CONFIG = pdfkit.configuration(wkhtmltopdf=PATH_TO_WKHTMLTOPDF)
OPT = {
    'margin-top': '2in',
    'margin-bottom': '1in',
    'margin-left': '1in',
    'margin-right': '1in',
    'page-size' : 'Letter'
}
TEMP_PDF_PATH = "./PDF/temp.pdf"
FINAL_PDF_PATH = "./PDF/output.pdf"
UID = str(uuid.uuid4())

def count_pdf_pages(temp_pdf_path):
    with open(temp_pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        num_pages = len(pdf_reader.pages)
    return num_pages

def get_ar_marker_coordinates(pdf_path):
    # Open the PDF file
    pdf_document = fitz.open(pdf_path)
    _image_list = pdf_document.get_page_images(pno=0, full=True)
    ar_marker_coordinates = pdf_document[0].get_image_rects(_image_list[0][7], transform=True)[0][0]
    # Close the PDF document
    pdf_document.close()
    return ar_marker_coordinates

def making_pdf_qr(path):
    pdfkit.from_url(path, output_path=TEMP_PDF_PATH, configuration=CONFIG, options=OPT, verbose=False)

    NUM_PAGES = count_pdf_pages(TEMP_PDF_PATH)

    folder_path = "./QR"

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    output_path = "./PDF"
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        
    uid_folder_path = os.path.join(folder_path, UID)
    if not os.path.exists(uid_folder_path):
        os.makedirs(uid_folder_path)

    for p_no in range(NUM_PAGES):
        text = '''{{
                "id": "{}",
                "page": {}
            }}'''.format(UID, (p_no))
        # Create QR code instance
        qr = qrcode.QRCode(
            version = 1,
            error_correction = qrcode.constants.ERROR_CORRECT_L,
            box_size = 10,
            border = 4,
        )

        # Add data to QR code
        qr.add_data(text)
        qr.make(fit=True)
        
        # Create an image from the QR Code instance
        img = qr.make_image(fill='black', back_color='white')
        
        # Save the image
        ext = ".png"
        file_name = os.path.join(uid_folder_path, str(p_no) + ext)
        img.save(file_name)

    
    # Making the pdf
    pdf_reader = PdfReader(TEMP_PDF_PATH)
    pdf_writer = PdfWriter()

    a = 200
    b = 660
    wid = 120
    hei = 120

    for i in range(NUM_PAGES):
        page = pdf_reader.pages[i]

        # Fetch the corresponding QR code image and AR marker
        qr_filename = "{}.png".format(i)
        qr_path = os.path.join(uid_folder_path, qr_filename)
        ar_marker_path = './_ARMarker/Markers/MarkerIcons03.png'
        
        
        with open(ar_marker_path, 'rb') as marker_file:
            marker_data = marker_file.read()
            marker_base64 = base64.b64encode(marker_data).decode('utf-8')

        # Check if QR code file exists
        if os.path.exists(qr_path):
            # Convert the QR image to a base64-encoded string
            with open(qr_path, 'rb') as qr_file:
                qr_data = qr_file.read()
                qr_base64 = base64.b64encode(qr_data).decode('utf-8')
                
            # Combine QR code with AR marker
        # Create a PDF page from the PNG images
        image_pdf_path = 'image_page.pdf'
        c = canvas.Canvas(image_pdf_path, pagesize=letter)
        # Draw the AR marker
        c.drawImage("data:image/png;base64," + marker_base64, a, b, width=wid, height=hei)
        # Draw the QR code
        c.drawImage("data:image/png;base64," + qr_base64, a + wid + 5, b, width=wid, height=hei)
        c.save()
        
        
        # Merge the image page with the current page of the original PDF
        with open(image_pdf_path, 'rb') as image_pdf_file:
            image_pdf_reader = PdfReader(image_pdf_file)
            image_page = image_pdf_reader.pages[0]
            page.merge_page(image_page)
            pdf_writer.add_page(page)

        os.remove(image_pdf_path)  
        
    with open(FINAL_PDF_PATH, 'wb') as output_pdf:
        pdf_writer.write(output_pdf)

    os.remove(TEMP_PDF_PATH)

    ar_marker_coordinates = get_ar_marker_coordinates(FINAL_PDF_PATH)
    doc = fitz.open(FINAL_PDF_PATH)
    json_data = {}
    json_data['ar_marker_coordinates'] = [a, (792 - (b + hei)), (a + wid), (792 - b)]
    json_data['pages'] = []

    # Get the total page count
    total_pages = doc.page_count

    for page_idx in range(total_pages):
        cur_page = doc.load_page(page_idx)
        links = cur_page.get_links()

        # Convert the list of dictionaries to the required format
        hyperlinks = []

        for item in links:
            x0, y0, x1, y1 = item['from']
            coordinates = [round(coord, 5) for coord in [x0, y0, x1, y1]]
            uri = item.get('uri', '')
            hyperlink = {'uri': uri, 'coordinates': coordinates}
            hyperlinks.append(hyperlink)

        # Create the final dictionary
        json_data['pages'].append({"hyperlinks": hyperlinks})

    doc.close()
    shutil.rmtree(folder_path)

    # Authentication
    with open('access.txt', 'r') as file:
        access_token = file.read().strip()
    github = Github(access_token)
    # Get the repository
    repo = github.get_repo('seanscofield/archivist')
    # File content
    file_content = json.dumps(json_data)
    # File path and name
    file_path = f'Assets/CustomAssets/{UID}.json'
    repo.create_file(file_path, "Added entry", file_content)

def process_pdf_file(file_path):
    pdf_reader = PdfReader(file_path)
    pdf_writer = PdfWriter()

    NUM_PAGES = len(pdf_reader.pages)

    folder_path = "./QR"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    uid_folder_path = os.path.join(folder_path, UID)
    if not os.path.exists(uid_folder_path):
        os.makedirs(uid_folder_path)

    for p_no in range(NUM_PAGES):
        text = '''{{
                "id": "{}",
                "page": {}
            }}'''.format(UID, (p_no + 1))
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        ext = ".png"
        file_name = os.path.join(uid_folder_path, str(p_no) + ext)
        img.save(file_name)

    a = 200
    b = 660
    wid = 120
    hei = 120
    
    for i in range(NUM_PAGES):
        page = pdf_reader.pages[i]
        qr_filename = "{}.png".format(i)
        qr_path = os.path.join(uid_folder_path, qr_filename)
        ar_marker_path = './_ARMarker/Markers/MarkerIcons03.png'
        with open(ar_marker_path, 'rb') as marker_file:
            marker_data = marker_file.read()
            marker_base64 = base64.b64encode(marker_data).decode('utf-8')

        if os.path.exists(qr_path):
            with open(qr_path, 'rb') as qr_file:
                qr_data = qr_file.read()
                qr_base64 = base64.b64encode(qr_data).decode('utf-8')

        image_pdf_path = 'image_page.pdf'
        c = canvas.Canvas(image_pdf_path, pagesize=letter)
        c.drawImage("data:image/png;base64," + marker_base64, a, b, width=wid, height=hei)
        # Draw the QR code
        c.drawImage("data:image/png;base64," + qr_base64, a + wid + 5, b, width=wid, height=hei)
        c.save()

        with open(image_pdf_path, 'rb') as image_pdf_file:
            image_pdf_reader = PdfReader(image_pdf_file)
            image_page = image_pdf_reader.pages[0]
            page.merge_page(image_page)
            pdf_writer.add_page(page)

        os.remove(image_pdf_path)

    with open(FINAL_PDF_PATH, 'wb') as output_pdf:
        pdf_writer.write(output_pdf)

    ar_marker_coordinates = get_ar_marker_coordinates(FINAL_PDF_PATH)
    doc = fitz.open(FINAL_PDF_PATH)

    json_data = {}
    json_data['ar_marker_coordinates'] = [ar_marker_coordinates.x0, ar_marker_coordinates.y0,
                                          ar_marker_coordinates.x1, ar_marker_coordinates.y1]
    json_data['pages'] = []
    total_pages = doc.page_count
    item_count = 0

    for page_idx in range(total_pages):
        cur_page = doc.load_page(page_idx)
        links = cur_page.get_links()
        hyperlinks = []

        for item in links:
            x0, y0, x1, y1 = item['from']
            coordinates = [round(coord, 5) for coord in [x0, y0, x1, y1]]
            uri = item.get('uri', '')
            hyperlink = {'id': UID + "-" + str(item_count), 'uri': uri, 'coordinates': coordinates}
            hyperlinks.append(hyperlink)
            item_count += 1

        json_data['pages'].append({"hyperlinks": hyperlinks})
    doc.close()

    # Authentication
    with open('access.txt', 'r') as file:
        access_token = file.read().strip()
    github = Github(access_token)
    # Get the repository
    repo = github.get_repo('seanscofield/archivist')
    # File content
    file_content = json.dumps(json_data)
    # File path and name
    file_path = f'Assets/CustomAssets/{UID}.json'
    repo.create_file(file_path, "Added entry", file_content)

class PDFGeneratorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('PDF Generator with QR Codes')
        self.layout = QVBoxLayout()
        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText('Enter URL')
        self.layout.addWidget(self.url_input)
        self.browse_button = QPushButton('Browse PDF', self)
        self.browse_button.clicked.connect(self.browse_pdf)
        self.layout.addWidget(self.browse_button)
        self.generate_button = QPushButton('Generate PDF from URL', self)
        self.generate_button.clicked.connect(self.generate_pdf_from_url)
        self.layout.addWidget(self.generate_button)
        self.status_label = QLabel('', self)
        self.layout.addWidget(self.status_label)
        self.setLayout(self.layout)

    def browse_pdf(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_path, _ = QFileDialog.getOpenFileName(self, "Open HTML File", "", "HTML Files (*.html);;All Files (*)", options=options)
        if file_path:
            self.status_label.setText('Processing File...')
            try:
                process_pdf_file(file_path)
                self.status_label.setText('File processed successfully!')
                QMessageBox.information(self, 'Success', 'File processed successfully!', QMessageBox.Ok)
            except Exception as e:
                self.status_label.setText('Error processing the file.')
                QMessageBox.critical(self, 'Error', f'Error processing the file: {e}', QMessageBox.Ok)

    def generate_pdf_from_url(self):
        url = self.url_input.text()
        if url:
            self.status_label.setText('Generating PDF...')
            try:
                making_pdf_qr(url)
                self.status_label.setText('PDF generated successfully!')
                QMessageBox.information(self, 'Success', 'PDF generated successfully!', QMessageBox.Ok)
            except Exception as e:
                self.status_label.setText('Error generating PDF.')
                QMessageBox.critical(self, 'Error', f'Error generating PDF: {e}', QMessageBox.Ok)
        else:
            QMessageBox.warning(self, 'Input Error', 'Please enter a valid URL.', QMessageBox.Ok)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PDFGeneratorApp()
    ex.show()
    sys.exit(app.exec_())