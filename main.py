import os
import time
import asyncio
import platform
import psutil
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Server & PC Health Monitor")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Глобальные переменные для подсчета скорости сети
prev_net_io = psutil.net_io_counters()
prev_time = time.time()


def get_system_metrics():
    global prev_net_io, prev_time

    # CPU
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_cores = psutil.cpu_percent(percpu=True, interval=None)

    # RAM
    ram = psutil.virtual_memory()
    ram_total_gb = round(ram.total / (1024 ** 3), 2)
    ram_used_gb = round(ram.used / (1024 ** 3), 2)
    ram_free_gb = round(ram.available / (1024 ** 3), 2)

    # Disks
    disks = []
    for part in psutil.disk_partitions(all=False):
        if os.name == 'nt' and ('cdrom' in part.opts or part.fstype == ''):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "total_gb": round(usage.total / (1024 ** 3), 1),
                "used_gb": round(usage.used / (1024 ** 3), 1),
                "free_gb": round(usage.free / (1024 ** 3), 1),
                "percent": usage.percent
            })
        except PermissionError:
            continue

    # Network Speed
    curr_net_io = psutil.net_io_counters()
    curr_time = time.time()
    dt = max(0.1, curr_time - prev_time)

    bytes_sent_per_sec = (curr_net_io.bytes_sent - prev_net_io.bytes_sent) / dt
    bytes_recv_per_sec = (curr_net_io.bytes_recv - prev_net_io.bytes_recv) / dt

    prev_net_io = curr_net_io
    prev_time = curr_time

    # Top processes
    top_processes = []
    for p in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                    key=lambda x: (x.info['cpu_percent'] or 0), reverse=True)[:5]:
        top_processes.append({
            "pid": p.info['pid'],
            "name": p.info['name'],
            "cpu": round(p.info['cpu_percent'] or 0.0, 1),
            "ram": round(p.info['memory_percent'] or 0.0, 1)
        })

    # Uptime
    boot_time = psutil.boot_time()
    uptime_sec = int(time.time() - boot_time)
    hours, rem = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(rem, 60)
    uptime_str = f"{hours}ч {minutes}м {seconds}с"

    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "uptime": uptime_str,
        "cpu": {
            "overall": cpu_percent,
            "cores": cpu_cores,
            "count": psutil.cpu_count(logical=True)
        },
        "ram": {
            "percent": ram.percent,
            "used_gb": ram_used_gb,
            "total_gb": ram_total_gb,
            "free_gb": ram_free_gb
        },
        "disks": disks,
        "network": {
            "upload_kbps": round(bytes_sent_per_sec / 1024, 1),
            "download_kbps": round(bytes_recv_per_sec / 1024, 1),
            "total_sent_mb": round(curr_net_io.bytes_sent / (1024 ** 2), 1),
            "total_recv_mb": round(curr_net_io.bytes_recv / (1024 ** 2), 1)
        },
        "processes": top_processes
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/stats")
async def stats_endpoint():
    return JSONResponse(get_system_metrics())


@app.websocket("/ws")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            metrics = get_system_metrics()
            await websocket.send_json(metrics)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    # Инициализация psutil для точного первого замера
    psutil.cpu_percent(interval=None)
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=False)
