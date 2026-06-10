import platform
import socket
from datetime import datetime

import psutil


class Device:
    def __init__(self, name, device_type):
        self.name = name
        self.device_type = device_type

        # stan dynamiczny
        self.status = "offline"
        self.last_seen = None
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        self.swap_usage = 0.0
        self.temperature = 0.0
        self.power_consumption = 0.0
        self.network_status = "disconnected"
        self.running_processes = 0
        self.disk_usage_percent = 0.0
        self.uptime_seconds = 0
        

        # sprzęt (statyczne)
        self.cpu_name = "unknown"
        self.cpu_cores = 0
        self.ram_gb = 0.0
        self.swap_total_gb = 0.0
        self.storage_gb = 0.0
        self.motherboard = "unknown"
        self.os = "unknown"
        self.ip_address = ""
        self.mac_address = ""
        self.vpn_status = "disconnected"
        self.vpn_address = ""
        self.gpu_info = "unknown"

    def __str__(self):
        return f"{self.device_type} named {self.name}"



    def fetch_info(self):
        """Pobiera statyczne informacje o sprzęcie —  raz przy starcie."""
        self.cpu_name = platform.processor() or platform.machine()
        self.cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count()
        self.ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
        self.swap_total_gb = round(psutil.swap_memory().total / (1024 ** 3), 1)
        self.storage_gb = round(psutil.disk_usage('/').total / (1024 ** 3), 1)
        self.os = f"{platform.system()} {platform.release()}"
        self.motherboard = platform.node()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.ip_address = s.getsockname()[0]
            s.close()
        except OSError:
            self.ip_address = "127.0.0.1"



    def update_status(self):
        """Aktualizuje dynamiczne metryki urządzenia (CPU%, RAM%, swap, temp, sieć)."""
        self.cpu_usage = psutil.cpu_percent(interval=1)
        self.ram_usage = psutil.virtual_memory().percent
        self.swap_usage = psutil.swap_memory().percent
        self.disk_usage_percent = psutil.disk_usage('/').percent
        self.running_processes = len(psutil.pids())
        self.uptime_seconds = int(datetime.now().timestamp() - psutil.boot_time())

        temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        if temps:
            all_readings = [t.current for readings in temps.values() for t in readings]
            self.temperature = round(sum(all_readings) / len(all_readings), 1) if all_readings else 0.0

        stats = psutil.net_if_stats()
        up_ifaces = [name for name, s in stats.items() if s.isup and name != "lo"]
        self.network_status = "connected" if up_ifaces else "disconnected"

        self.status = "online"
        self.last_seen = datetime.now()



    def display_info(self):
        """Wyświetla informacje o urządzeniu."""
        seen = self.last_seen.strftime("%Y-%m-%d %H:%M:%S") if self.last_seen else "never"
        print(f"[{self.name}] {self.device_type} | {self.status}")
        print(f"  CPU:  {self.cpu_name} ({self.cpu_cores} cores)  |  {self.cpu_usage}%")
        print(f"  RAM:  {self.ram_gb} GB  |  {self.ram_usage}%")
        print(f"  Swap: {self.swap_total_gb} GB  |  {self.swap_usage}%")
        print(f"  Disk: {self.storage_gb} GB  |  {self.disk_usage_percent}%")
        print(f"  OS:   {self.os}")
        print(f"  IP:   {self.ip_address}")
        print(f"  Net:  {self.network_status}")
        print(f"  Seen: {seen}")
