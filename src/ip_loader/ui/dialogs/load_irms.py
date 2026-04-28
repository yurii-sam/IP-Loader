from PySide6.QtWidgets import QListWidgetItem, QDialogButtonBox
from PySide6.QtCore import QFile, Qt
from PySide6.QtUiTools import QUiLoader
from .base import VIEWS_DIR

class LoadIrmsDialogController:
    def __init__(self, loaded_ips, fetch_callback, parent=None):
        self.fetch_callback = fetch_callback

        loader = QUiLoader()
        ui_path = VIEWS_DIR / "load_irms_dialog.ui"
        ui_file = QFile(str(ui_path))
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
