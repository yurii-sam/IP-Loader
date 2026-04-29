from PySide6.QtWidgets import QFileDialog
from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from .base import VIEWS_DIR

class SettingsDialogController:
    def __init__(self, config_manager, parent=None):
        self.config_manager = config_manager
        loader = QUiLoader()
        ui_path = VIEWS_DIR / "settings_dialog.ui"
        ui_file = QFile(str(ui_path))
        ui_file.open(QFile.ReadOnly)
        self.dialog = loader.load(ui_file, parent)
        ui_file.close()

        self.load_settings()
        self.connect_signals()

    def load_settings(self):
        theme = self.config_manager.get("theme")
        index = self.dialog.comboTheme.findText(theme)
        if index >= 0:
            self.dialog.comboTheme.setCurrentIndex(index)
        
        self.dialog.checkIRM.setChecked(self.config_manager.get("default_load_irms"))
        self.dialog.checkSOI.setChecked(self.config_manager.get("default_load_soi"))
        self.dialog.lineOpenAI.setText(self.config_manager.get("openai_token"))
        self.dialog.lineProjectFolder.setText(self.config_manager.get("projects_folder"))

    def connect_signals(self):
        self.dialog.btnBrowseFolder.clicked.connect(self.browse_folder)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self.dialog, "Select Projects Folder", self.dialog.lineProjectFolder.text())
        if folder:
            self.dialog.lineProjectFolder.setText(folder)

    def save_settings(self):
        self.config_manager.set("theme", self.dialog.comboTheme.currentText())
        self.config_manager.set("default_load_irms", self.dialog.checkIRM.isChecked())
        self.config_manager.set("default_load_soi", self.dialog.checkSOI.isChecked())
        self.config_manager.set("openai_token", self.dialog.lineOpenAI.text())
        self.config_manager.set("projects_folder", self.dialog.lineProjectFolder.text())

    def exec(self):
        if self.dialog.exec():
            self.save_settings()
            return True
        return False
