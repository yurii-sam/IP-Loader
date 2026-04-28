import sys
import os

# Add src to sys.path so we can import ip_loader
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.ip_loader.app import ApplicationController

if __name__ == "__main__":
    controller = ApplicationController()
    sys.exit(controller.run())
