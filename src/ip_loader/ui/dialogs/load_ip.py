import openpyxl
from PySide6.QtWidgets import (
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox
)
from PySide6.QtCore import QFile, Qt
from PySide6.QtUiTools import QUiLoader
from .base import VIEWS_DIR

class LoadIpDialogController:
    def __init__(self, parent=None):
        loader = QUiLoader()
        ui_path = VIEWS_DIR / "load_ip_dialog.ui"
        ui_file = QFile(str(ui_path))
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
