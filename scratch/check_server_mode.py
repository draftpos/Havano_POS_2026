import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.company_defaults import get_defaults
from services.credentials import get_system_mode

defaults = get_defaults()
print("System Mode:", get_system_mode())
print("Server URL:", defaults.get("server_url"))
print("POS Profile:", defaults.get("server_pos_profile"))
print("Terminal ID:", defaults.get("server_terminal_id"))
print("Shop:", defaults.get("server_shop_name"))
