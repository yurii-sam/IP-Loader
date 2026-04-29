import json
from pathlib import Path
from PySide6.QtCore import QStandardPaths

class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".ip_loader"
        self.config_path = self.config_dir / "config.json"
        
        docs_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        default_projects = Path(docs_path) / "IP_Projects"

        self.defaults = {
            "theme": "System Default",
            "default_load_irms": False,
            "default_load_soi": False,
            "openai_token": "",
            "projects_folder": str(default_projects),
            "last_project_path": ""
        }
        self.config = self.defaults.copy()
        self.load()

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key):
        return self.config.get(key, self.defaults.get(key))

    def set(self, key, value):
        self.config[key] = value
        self.save()
