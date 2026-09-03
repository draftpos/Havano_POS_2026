import subprocess, os

output = subprocess.check_output('wmic process get processid,commandline,name /format:csv', shell=True).decode('utf-8', errors='ignore')

current_pid = str(os.getpid())
killed = []

for line in output.splitlines():
    parts = line.strip().split(',')
    if len(parts) >= 4:
        cmdline = parts[1]
        name = parts[2].lower()
        pid = parts[3].strip()
        
        if pid == current_pid or not pid.isdigit():
            continue
            
        if ("python" in name and "main.py" in cmdline.lower()) or ("havanopos" in name) or ("havano_pos" in cmdline.lower() and "kill_services" not in cmdline.lower()):
            try:
                subprocess.call(f'taskkill /F /PID {pid}', shell=True)
                killed.append(f"{parts[2]} (PID {pid})")
            except Exception as e:
                pass

print("Terminated processes:", killed if killed else "None running.")
