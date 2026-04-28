import csv
import openpyxl
from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import QFileInfo, QUrl
from PySide6.QtGui import QDesktopServices

class PreviewPanel:
    def __init__(self, window, log_callback):
        self.window = window
        self.log = log_callback
        self.current_preview_path = None

    def handle_file_selection(self, file_path):
        file_info = QFileInfo(file_path)

        if file_info.isDir():
            return

        self.current_preview_path = file_path
        extension = file_info.suffix().lower()

        if extension == "html":
            self.window.previewStack.setCurrentIndex(0)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.window.htmlPreviewer.setHtml(f.read())
            except Exception as e:
                self.window.htmlPreviewer.setPlainText(f"Error reading HTML:\n{str(e)}")

        elif extension == "pdf":
            self.window.previewStack.setCurrentIndex(1)
            self.window.labelPdfNotice.setText(f"<b>3D PDF Selected:</b><br>{file_info.fileName()}")

        elif extension == "csv":
            self.window.previewStack.setCurrentIndex(2)
            self.window.labelDataNotice.setText(f"Previewing CSV: {file_info.fileName()} (First 500 rows)")
            self.preview_csv(file_path)

        elif extension in ["xlsx", "xls"]:
            self.window.previewStack.setCurrentIndex(2)
            self.window.labelDataNotice.setText(f"Previewing Excel: {file_info.fileName()} (First 500 rows)")
            self.preview_excel(file_path)

        else:
            self.window.previewStack.setCurrentIndex(0)
            self.window.htmlPreviewer.setHtml(f"<h2>File Selected</h2><p>{file_info.fileName()}</p>")

    def preview_csv(self, file_path):
        self.window.dataPreviewTable.clear()
        self.window.dataPreviewTable.setRowCount(0)
        self.window.dataPreviewTable.setColumnCount(0)

        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                data = list(reader)

                if not data:
                    return

                # Cap at 500 to prevent GUI lockups
                preview_data = data[:500]

                self.window.dataPreviewTable.setColumnCount(len(preview_data[0]))
                self.window.dataPreviewTable.setRowCount(len(preview_data))

                for row_idx, row_data in enumerate(preview_data):
                    for col_idx, cell_data in enumerate(row_data):
                        self.window.dataPreviewTable.setItem(row_idx, col_idx, QTableWidgetItem(str(cell_data)))
        except Exception as e:
            self.log(f"Failed to preview CSV: {str(e)}")

    def preview_excel(self, file_path):
        self.window.dataPreviewTable.clear()
        self.window.dataPreviewTable.setRowCount(0)
        self.window.dataPreviewTable.setColumnCount(0)

        try:
            # read_only mode is critical here for performance on large files
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            sheet = wb.active

            data = []
            for row in sheet.iter_rows(values_only=True, max_row=500):
                data.append(row)

            if not data:
                return

            # Find the widest row in case the data is jagged
            max_cols = max(len(r) for r in data if r)
            self.window.dataPreviewTable.setColumnCount(max_cols)
            self.window.dataPreviewTable.setRowCount(len(data))

            for row_idx, row_data in enumerate(data):
                if not row_data:
                    continue
                for col_idx, cell_data in enumerate(row_data):
                    val = str(cell_data) if cell_data is not None else ""
                    self.window.dataPreviewTable.setItem(row_idx, col_idx, QTableWidgetItem(val))

        except Exception as e:
            self.log(f"Failed to preview Excel file: {str(e)}")

    def open_external_pdf(self):
        if self.current_preview_path:
            # This asks the OS to open the file with whatever default app the user has registered
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.current_preview_path))
            self.log(f"Opened externally: {QFileInfo(self.current_preview_path).fileName()}")

    def clear_preview(self):
        self.window.previewStack.setCurrentIndex(0)
        self.window.htmlPreviewer.setHtml("<h2>File Deleted</h2>")
        self.current_preview_path = None
