import difflib
from PySide6.QtWidgets import (
    QTableWidgetItem, QHeaderView, QListWidgetItem, QDialogButtonBox
)
from PySide6.QtCore import QFile, Qt
from PySide6.QtUiTools import QUiLoader

import openpyxl
from PySide6.QtWidgets import (
    QTableWidgetItem, QHeaderView, QDialogButtonBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import QFile, Qt
from PySide6.QtUiTools import QUiLoader


class LoadIpDialogController:
    def __init__(self, parent=None):
        loader = QUiLoader()
        ui_file = QFile("UI/load_ip_dialog.ui")
        ui_file.open(QFile.ReadOnly)
        self.dialog = loader.load(ui_file, parent)
        ui_file.close()

        self.setup_table()
        self.connect_signals()

    def setup_table(self):
        header = self.dialog.tableWidget.horizontalHeader()

        # IP stretches, LN is fixed so it doesn't squish into oblivion
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.dialog.tableWidget.setColumnWidth(1, 80)

        self.add_row()

    def connect_signals(self):
        self.dialog.btnAddRow.clicked.connect(self.add_row)
        self.dialog.btnRemoveRow.clicked.connect(self.remove_selected_row)
        # Connected to the new Excel button name
        self.dialog.btnLoadExcel.clicked.connect(self.load_from_excel)

    def add_row(self, ip_val="", ln_val=""):
        row_count = self.dialog.tableWidget.rowCount()
        self.dialog.tableWidget.insertRow(row_count)

        ip_item = QTableWidgetItem(ip_val)
        ln_item = QTableWidgetItem(ln_val)
        self.dialog.tableWidget.setItem(row_count, 0, ip_item)
        self.dialog.tableWidget.setItem(row_count, 1, ln_item)

        irm_check = QTableWidgetItem()
        irm_check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        irm_check.setCheckState(Qt.Unchecked)
        self.dialog.tableWidget.setItem(row_count, 2, irm_check)

        soi_check = QTableWidgetItem()
        soi_check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        soi_check.setCheckState(Qt.Unchecked)
        self.dialog.tableWidget.setItem(row_count, 3, soi_check)

    def remove_selected_row(self):
        current_row = self.dialog.tableWidget.currentRow()
        if current_row >= 0:
            self.dialog.tableWidget.removeRow(current_row)

    def load_from_excel(self):
        # Filter for native .xlsx files
        file_path, _ = QFileDialog.getOpenFileName(
            self.dialog, "Open Excel File", "", "Excel Files (*.xlsx);;All Files (*)"
        )

        if not file_path:
            return

        try:
            # data_only=True ensures we get the results of formulas, not the formulas themselves
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet = wb.active

            # Clear out the initial empty row if the table is totally blank
            if self.dialog.tableWidget.rowCount() == 1:
                first_ip = self.dialog.tableWidget.item(0, 0).text()
                first_ln = self.dialog.tableWidget.item(0, 1).text()
                if not first_ip and not first_ln:
                    self.dialog.tableWidget.removeRow(0)

            # We assume Column A is IP, Column B is LN
            for row in sheet.iter_rows(values_only=True):
                # Check if row has data and the first cell isn't totally blank
                if len(row) >= 2 and row[0] is not None:
                    ip_val = str(row[0]).strip()
                    ln_val = str(row[1]).strip() if row[1] is not None else ""

                    # Basic header skip: if LN isn't a number, it's probably a title row
                    if not ln_val.isdigit() and len(ip_val) > 0:
                        continue

                    self.add_row(ip_val, ln_val)

        except Exception as e:
            QMessageBox.critical(self.dialog, "Error Reading File", f"Could not parse Excel file:\n{str(e)}")

    def get_data(self):
        data = []
        for row in range(self.dialog.tableWidget.rowCount()):
            ip_text = self.dialog.tableWidget.item(row, 0).text().strip()
            ln_text = self.dialog.tableWidget.item(row, 1).text().strip()

            if not ip_text and not ln_text:
                continue

            irm_checked = self.dialog.tableWidget.item(row, 2).checkState() == Qt.Checked
            soi_checked = self.dialog.tableWidget.item(row, 3).checkState() == Qt.Checked

            data.append({
                "ip": ip_text,
                "ln": ln_text,
                "load_irms": irm_checked,
                "load_soi": soi_checked
            })
        return data

    def exec(self):
        return self.dialog.exec()

class LoadIrmsDialogController:
    def __init__(self, loaded_ips, fetch_callback, parent=None):
        self.fetch_callback = fetch_callback

        loader = QUiLoader()
        ui_file = QFile("UI/load_irms_dialog.ui")
        ui_file.open(QFile.ReadOnly)
        self.dialog = loader.load(ui_file, parent)
        ui_file.close()

        self.btn_ok = self.dialog.buttonBox.button(QDialogButtonBox.Ok)
        self.btn_ok.setText("Load Selected")
        self.btn_ok.setEnabled(False)

        self.setup_ui(loaded_ips)
        self.connect_signals()

    def setup_ui(self, loaded_ips):
        self.dialog.comboIpLn.addItems(loaded_ips)
        if loaded_ips:
            self.load_parts_for_ip(loaded_ips[0])

    def connect_signals(self):
        self.dialog.comboIpLn.currentTextChanged.connect(self.load_parts_for_ip)
        self.dialog.listParts.itemChanged.connect(self.validate_selection)

    def load_parts_for_ip(self, ip_ln):
        self.dialog.listParts.clear()

        loading_item = QListWidgetItem("Fetching parts list...")
        loading_item.setFlags(Qt.NoItemFlags)
        self.dialog.listParts.addItem(loading_item)

        self.btn_ok.setEnabled(False)
        self.fetch_callback(ip_ln)

    def populate_parts(self, parts_list):
        self.dialog.listParts.clear()

        if not parts_list:
            empty_item = QListWidgetItem("No parts found.")
            empty_item.setFlags(Qt.NoItemFlags)
            self.dialog.listParts.addItem(empty_item)
            return

        for part in parts_list:
            item = QListWidgetItem(part)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.dialog.listParts.addItem(item)

        self.validate_selection()

    def validate_selection(self):
        has_selection = False
        for i in range(self.dialog.listParts.count()):
            if self.dialog.listParts.item(i).checkState() == Qt.Checked:
                has_selection = True
                break

        self.btn_ok.setEnabled(has_selection)

    def get_data(self):
        selected_ip = self.dialog.comboIpLn.currentText()
        selected_parts = []

        for i in range(self.dialog.listParts.count()):
            item = self.dialog.listParts.item(i)
            if item.checkState() == Qt.Checked:
                selected_parts.append(item.text())

        return {
            "ip_ln": selected_ip,
            "parts": selected_parts
        }

    def exec(self):
        return self.dialog.exec()


class LoadSoiDialogController:
    def __init__(self, loaded_ips, parent=None):
        loader = QUiLoader()
        ui_file = QFile("UI/load_soi_dialog.ui")
        ui_file.open(QFile.ReadOnly)
        self.dialog = loader.load(ui_file, parent)
        ui_file.close()

        self.dialog.comboIpLn.addItems(loaded_ips)

        if not loaded_ips:
            self.dialog.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)

    def get_data(self):
        return self.dialog.comboIpLn.currentText()

    def exec(self):
        return self.dialog.exec()


import re
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtCore import QFile, Qt
from PySide6.QtUiTools import QUiLoader


class CompareSoiDialogController:
    def __init__(self, loaded_ips, project_mgr, parent=None):
        self.project_mgr = project_mgr

        loader = QUiLoader()
        ui_file = QFile("UI/compare_soi_dialog.ui")
        ui_file.open(QFile.ReadOnly)
        self.dialog = loader.load(ui_file, parent)
        ui_file.close()

        self.setup_ui(loaded_ips)
        self.connect_signals()

    def setup_ui(self, loaded_ips):
        self.dialog.comboSource.addItems(loaded_ips)
        self.dialog.comboTarget.addItems(loaded_ips)

        if len(loaded_ips) > 1:
            self.dialog.comboTarget.setCurrentIndex(1)

        self.dialog.verticalSplitter.setSizes([600, 200])

    def connect_signals(self):
        self.dialog.btnRunDiff.clicked.connect(self.run_diff)
        self.dialog.btnGenerateAi.clicked.connect(self.generate_ai_summary)

        # Synchronize the vertical scrolling of both rendered HTML pages
        scroll_source = self.dialog.textSource.verticalScrollBar()
        scroll_target = self.dialog.textTarget.verticalScrollBar()

        scroll_source.valueChanged.connect(scroll_target.setValue)
        scroll_target.valueChanged.connect(scroll_source.setValue)

    def fetch_soi_text(self, ip_ln):
        return self.project_mgr.get_soi_text(ip_ln)

    def clean_html_for_render(self, html_text):
        """
        Aggressively strips invisible legacy garbage so the QTextBrowser
        doesn't waste memory rendering massive blocks of hidden data.
        """
        if not html_text:
            return ""

        # Nuke all HTML comments
        html_text = re.sub(r'', '', html_text)

        # Nuke custom XML tags like <RevisionHistory>
        html_text = re.sub(r'<RevisionHistory[\s\S]*?</RevisionHistory>', '', html_text, flags=re.IGNORECASE)

        # Nuke inline JavaScript (QTextBrowser ignores it anyway, but it saves memory)
        html_text = re.sub(r'<script[\s\S]*?</script>', '', html_text, flags=re.IGNORECASE)

        # Nuke massive ASP.NET state variables
        html_text = re.sub(r'<input type="hidden" name="__VIEWSTATE.*?>', '', html_text, flags=re.IGNORECASE)
        html_text = re.sub(r'<input type="hidden" name="__EVENTVALIDATION.*?>', '', html_text, flags=re.IGNORECASE)

        return html_text

    def run_diff(self):
        source_ip = self.dialog.comboSource.currentText()
        target_ip = self.dialog.comboTarget.currentText()

        if not source_ip or not target_ip:
            return

        # Fetch the raw HTML files
        source_text = self.fetch_soi_text(source_ip)
        target_text = self.fetch_soi_text(target_ip)

        # Scrub the garbage
        source_clean = self.clean_html_for_render(source_text)
        target_clean = self.clean_html_for_render(target_text)

        # Render the HTML directly into the standard QTextBrowsers
        self.dialog.textSource.setHtml(source_clean)
        self.dialog.textTarget.setHtml(target_clean)

        self.dialog.btnGenerateAi.setEnabled(True)

    def generate_ai_summary(self):
        self.dialog.btnGenerateAi.setEnabled(False)
        self.dialog.textAiSummary.setHtml("<i>Contacting LLM... Generating summary of changes...</i>")
        # TODO: Fire off the worker to handle the LLM API call

    def exec(self):
        return self.dialog.exec()