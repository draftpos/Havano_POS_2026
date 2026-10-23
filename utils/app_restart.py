# utils/app_restart.py — Safe application process restart helper
import sys
import os
import subprocess
import logging
from pathlib import Path

log = logging.getLogger("app_restart")

def restart_application():
    """
    Safely unlocks Qt single-instance lock file, spawns a new instance of the application,
    and forcefully exits the current process.
    """
    # 1. Unlock PySide6 QLockFile across all module scopes
    try:
        for mod_name in ('__main__', 'main'):
            mod = sys.modules.get(mod_name)
            if mod:
                if hasattr(mod, "release_single_instance_lock"):
                    try:
                        mod.release_single_instance_lock()
                    except Exception:
                        pass
                if hasattr(mod, "_lock_file") and mod._lock_file:
                    try:
                        mod._lock_file.unlock()
                        mod._lock_file = None
                    except Exception:
                        pass
    except Exception:
        pass

    # 2. Attempt to remove lock file directly from disk
    try:
        from PySide6.QtCore import QDir
        lock_path = os.path.join(QDir.tempPath(), "havano_pos_2026.lock")
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except Exception:
                pass
    except Exception:
        pass

    # 3. Determine canonical project root and python / app executable
    try:
        project_root = Path(__file__).resolve().parent.parent
        main_py = str(project_root / "main.py")

        # Resolve python executable with priority for the project's virtualenv
        my_venv_python = project_root / "my" / "Scripts" / "python.exe"
        if my_venv_python.exists():
            exe = str(my_venv_python)
        else:
            exe = sys.executable
            venv_path = os.environ.get("VIRTUAL_ENV")
            if venv_path:
                venv_exe = os.path.join(venv_path, "Scripts", "python.exe") if os.name == "nt" else os.path.join(venv_path, "bin", "python")
                if os.path.exists(venv_exe):
                    exe = venv_exe

        if getattr(sys, "frozen", False):
            args = [sys.executable, "--restart"]
        else:
            args = [exe, main_py, "--restart"]

        log.info("[app_restart] Spawning clean process: %s (cwd=%s)", args, project_root)
        
        spawn_kwargs = {
            "cwd": str(project_root),
            "close_fds": True,
        }
        if os.name == "nt":
            spawn_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(args, **spawn_kwargs)
    except Exception as e:
        log.error("[app_restart] Subprocess relaunch error: %s", e)

    # 4. Small yield to let child process spawn before parent terminates
    try:
        import time
        time.sleep(0.15)
    except Exception:
        pass

    # 5. Terminate old process immediately to release ports and file handles
    os._exit(0)
