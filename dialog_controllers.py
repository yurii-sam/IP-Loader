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

import difflib
from html import escape
from PySide6.QtWidgets import (
    QTableWidgetItem, QHeaderView, QListWidgetItem, QDialogButtonBox,
    QFileDialog, QMessageBox, QWidget, QApplication
)
from PySide6.QtGui import QPainter, QColor, QPalette
from PySide6.QtCore import QFile, Qt
from PySide6.QtUiTools import QUiLoader


class DiffRuler(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(12)
        self.changes = []
        self.total_lines = 1

    def update_data(self, changes, total_lines):
        self.changes = changes
        self.total_lines = max(1, total_lines)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        # Check theme to set the track background color
        is_dark = self.palette().color(QPalette.WindowText).lightness() > self.palette().color(
            QPalette.Window).lightness()
        bg_color = QColor("#2b2b2b") if is_dark else QColor("#f0f0f0")
        painter.fillRect(self.rect(), bg_color)

        h = self.height()
        for change_type, line_idx in self.changes:
            y = int((line_idx / self.total_lines) * h)

            if change_type == 'delete':
                color = QColor("#ef9a9a")
            elif change_type == 'insert':
                color = QColor("#a5d6a7")
            else:
                color = QColor("#ffcc80")

            painter.fillRect(0, y, self.width(), 4, color)


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


def generate_aligned_html_diff(source_text, target_text, is_dark_mode=False):
    sm = difflib.SequenceMatcher(None, source_text.splitlines(), target_text.splitlines())
    left_html, right_html, changes = [], [], []
    current_line = 0

    # Theme-aware CSS
    if is_dark_mode:
        style_del = "background-color: #4a191b; color: #ffb3b3; text-decoration: line-through;"
        style_add = "background-color: #1a3320; color: #b3ffb3;"
        style_chg = "background-color: #4d3319; color: #ffd699;"
        style_pad = "background-color: #2b2b2b;"
        style_eq = "color: #e0e0e0; background-color: transparent;"
    else:
        style_del = "background-color: #ffebee; color: #b71c1c; text-decoration: line-through;"
        style_add = "background-color: #e8f5e9; color: #1b5e20;"
        style_chg = "background-color: #fff3e0; color: #e65100;"
        style_pad = "background-color: #f5f5f5;"
        style_eq = "color: #333333; background-color: transparent;"

    def format_line(line, style):
        safe_text = escape(line) if line else "&nbsp;"
        return f"<pre style='margin: 0; padding: 2px 4px; {style}'>{safe_text}</pre>"

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for line in source_text.splitlines()[i1:i2]:
                left_html.append(format_line(line, style_eq))
                right_html.append(format_line(line, style_eq))
                current_line += 1

        elif tag == 'replace':
            left_lines = source_text.splitlines()[i1:i2]
            right_lines = target_text.splitlines()[j1:j2]
            max_len = max(len(left_lines), len(right_lines))

            for i in range(max_len):
                if i < len(left_lines):
                    left_html.append(format_line(left_lines[i], style_chg))
                else:
                    left_html.append(format_line("", style_pad))

                if i < len(right_lines):
                    right_html.append(format_line(right_lines[i], style_chg))
                else:
                    right_html.append(format_line("", style_pad))

                changes.append(('change', current_line))
                current_line += 1

        elif tag == 'delete':
            for line in source_text.splitlines()[i1:i2]:
                left_html.append(format_line(line, style_del))
                right_html.append(format_line("", style_pad))
                changes.append(('delete', current_line))
                current_line += 1

        elif tag == 'insert':
            for line in target_text.splitlines()[j1:j2]:
                left_html.append(format_line("", style_pad))
                right_html.append(format_line(line, style_add))
                changes.append(('insert', current_line))
                current_line += 1

    return "".join(left_html), "".join(right_html), changes, current_line


class CompareSoiDialogController:
    def __init__(self, loaded_ips, project_mgr, parent=None):
        self.project_mgr = project_mgr

        loader = QUiLoader()
        ui_file = QFile("UI/compare_soi_dialog.ui")
        ui_file.open(QFile.ReadOnly)
        self.dialog = loader.load(ui_file, parent)
        ui_file.close()

        # Inject the custom ruler directly into the splitter layout
        self.ruler = DiffRuler(self.dialog)
        self.dialog.horizontalSplitter.addWidget(self.ruler)

        # Prevent the user from resizing the ruler
        self.dialog.horizontalSplitter.setStretchFactor(0, 1)  # Left Text
        self.dialog.horizontalSplitter.setStretchFactor(1, 1)  # Right Text
        self.dialog.horizontalSplitter.setStretchFactor(2, 0)  # Ruler

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

        scroll_source = self.dialog.textSource.verticalScrollBar()
        scroll_target = self.dialog.textTarget.verticalScrollBar()

        scroll_source.valueChanged.connect(scroll_target.setValue)
        scroll_target.valueChanged.connect(scroll_source.setValue)

    def fetch_soi_text(self, ip_ln):
        return self.project_mgr.get_soi_text(ip_ln)

    def run_diff(self):
        source_ip = self.dialog.comboSource.currentText()
        target_ip = self.dialog.comboTarget.currentText()

        if not source_ip or not target_ip:
            return

        source_text = self.fetch_soi_text(source_ip)
        target_text = self.fetch_soi_text(target_ip)

        # Detect the current theme before generating the HTML
        palette = QApplication.palette()
        is_dark = palette.color(QPalette.WindowText).lightness() > palette.color(QPalette.Window).lightness()

        # Pass the is_dark flag to the generator
        left_html, right_html, changes, total_lines = generate_aligned_html_diff(source_text, target_text, is_dark)

        self.dialog.textSource.setHtml(left_html)
        self.dialog.textTarget.setHtml(right_html)
        self.ruler.update_data(changes, total_lines)

        self.dialog.btnGenerateAi.setEnabled(True)

    def generate_ai_summary(self):
        self.dialog.btnGenerateAi.setEnabled(False)
        self.dialog.textAiSummary.setHtml("<i>Contacting LLM... Generating summary of changes...</i>")

        # Fire off the worker to handle the LLM API call

    def exec(self):
        return self.dialog.exec()