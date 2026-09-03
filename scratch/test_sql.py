import winreg
import socket
instances = []
try:
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL")
    for i in range(100):
        try:
            name, _, _ = winreg.EnumValue(key, i)
            instances.append(name)
        except OSError:
            break
except Exception as e:
    print("Error:", e)

hostname = socket.gethostname()
servers = []
for inst in instances:
    if inst.upper() == "MSSQLSERVER":
        servers.append(hostname)
        servers.append(r".")
        servers.append(r"localhost")
    else:
        servers.append(f"{hostname}\\{inst}")
        servers.append(f".\\{inst}")
        servers.append(f"localhost\\{inst}")

print("Servers:", servers)
