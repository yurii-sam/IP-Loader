import time
from pathlib import Path


class ProjectManager:
    def __init__(self, base_workspace_path):
        """
        Initializes the manager. base_workspace_path is usually your Documents/IP_Projects
        """
        self.base_path = Path(base_workspace_path)
        self.active_project_path = None

    def set_active_project(self, folder_path):
        """Sets the current working directory for the session."""
        path = Path(folder_path)
        if path.exists() and path.is_dir():
            self.active_project_path = path
            return True
        return False

    def create_new_project(self, project_name=None):
        """Creates a new Project-Date folder."""
        date_str = time.strftime("%Y-%m-%d")
        name = f"{project_name}-{date_str}" if project_name else f"Project-{date_str}"

        new_dir = self.base_path / name
        new_dir.mkdir(parents=True, exist_ok=True)
        self.active_project_path = new_dir
        return new_dir

    def get_loaded_ips(self):
        """
        Scans the active project folder and returns a list of loaded IP-LNs.
        This replaces the 'mock_loaded_ips' in the UI.
        """
        if not self.active_project_path:
            return []

        # Look for subdirectories that look like IP-LN pairs
        # You can add regex validation here later if needed
        ip_folders = [f.name for f in self.active_project_path.iterdir() if f.is_dir()]
        return sorted(ip_folders)

    def setup_ip_environment(self, ip, ln):
        """
        Creates the required internal hierarchy for an IP-LN pair:
        Project-Folder/
        -- IPNUMBER-LN/
        --- IRMs/
        """
        if not self.active_project_path:
            raise ValueError("No active project selected.")

        folder_name = f"{ip}-{ln}"
        ip_dir = self.active_project_path / folder_name
        irms_dir = ip_dir / "IRMs"

        ip_dir.mkdir(exist_ok=True)
        irms_dir.mkdir(exist_ok=True)

        return ip_dir

    def get_soi_text(self, ip_ln_string):
        """Reads the SOI.html file for a given IP-LN string to feed the diff window."""
        if not self.active_project_path:
            return "Error: No project open."

        soi_path = self.active_project_path / ip_ln_string / "SOI.html"

        if not soi_path.exists():
            return f"Error: No SOI.html found for {ip_ln_string}"

        with open(soi_path, 'r', encoding='utf-8') as f:
            return f.read()