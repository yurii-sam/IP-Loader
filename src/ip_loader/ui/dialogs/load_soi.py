from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from .base import VIEWS_DIR

class LoadSoiDialogController:
    def __init__(self, loaded_ips, parent=None):
        loader = QUiLoader()
        ui_path = VIEWS_DIR / "load_soi_dialog.ui"
        ui_file = QFile(str(ui_path))
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
