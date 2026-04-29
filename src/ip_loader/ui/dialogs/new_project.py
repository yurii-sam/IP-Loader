import time
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Enter project folder name:"))
        
        self.line_edit = QLineEdit(self)
        date_str = time.strftime("%Y-%m-%d")
        self.line_edit.setPlaceholderText(f"Project-{date_str}")
        self.line_edit.setText(f"Project-{date_str}")
        layout.addWidget(self.line_edit)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_project_name(self):
        return self.line_edit.text()
