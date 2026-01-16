import os, psutil, time, subprocess

APP_ROOT = "/home/qynix/public_html"
APP_PUBLIC = APP_ROOT
APP_PUBLIC = os.path.join(APP_ROOT, "public_html")
APPS_DIR = os.path.join(APP_PUBLIC, "Apps")
LOG_FILE = os.path.join(APP_PUBLIC, "logs/app.log")

# ---------------- Safe Actions ----------------


def restart_app(project):
    # Detached, ignoring Flask process
    subprocess.Popen("nohup /usr/local/bin/restart >/dev/null 2>&1 &", shell=True)
    return True

# ---------------- Stats ----------------
def get_uptime():
    return int(time.time() - psutil.boot_time())

def get_cpu():
    return psutil.cpu_percent(interval=0.3)

def get_ram():
    return psutil.virtual_memory().percent

def get_directory_size(path):
    """Get directory size using os.scandir (faster than os.walk)."""
    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
            elif entry.is_dir():
                try:
                    total += get_directory_size(entry.path)
                except OSError:
                    pass
    return total

def get_storage():
    used = get_directory_size(APP_ROOT)
    stat = os.statvfs(APP_ROOT)
    total = stat.f_blocks * stat.f_frsize
    percent = round((used / total) * 100, 2)
    return {"used": used, "total": total, "percent": percent}

# ---------------- Projects ----------------
def get_apps_storage():
    apps = []
    if not os.path.exists(APPS_DIR):
        return {"total":0,"apps":[]}

    for name in sorted(os.listdir(APPS_DIR)):
        path = os.path.join(APPS_DIR, name)
        if os.path.isdir(path):
            size = get_directory_size(path)
            mtime = max([os.path.getmtime(os.path.join(r,f)) for r,d,fs in os.walk(path) for f in fs], default=0)
            apps.append({"name": name, "size": size, "mtime": mtime})

    total = sum(a["size"] for a in apps)
    for a in apps:
        a["percent"] = round((a["size"]/total)*100,2) if total else 0
    return {"total": total, "apps": apps}

# ---------------- Logs ----------------
def get_logs(lines=50):
    if not os.path.exists(LOG_FILE):
        return "No logs found"
    with open(LOG_FILE) as f:
        return "".join(f.readlines()[-lines:])
