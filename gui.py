import os
import tkinter as tk
from tkinter import ttk, messagebox
import requests

PP_URL = os.environ.get("PP_COORDINATOR", "http://localhost:4200").rstrip("/")
PP_TOKEN = os.environ.get("PP_TOKEN", "test")

def get_headers():
    return {"X-Token": PP_TOKEN}

class PatientPredatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PatientPredator - Panel Sterowania (Dashboard)")
        self.root.geometry("850x600")
        
        # --- ZMIENNE ---
        self.server_status = tk.StringVar()
        self.server_status.set("Łączenie z serwerem...")
        
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self):
        # Górny pasek statusu
        status_frame = tk.Frame(self.root, pady=10)
        status_frame.pack(fill=tk.X, padx=10)
        
        tk.Label(status_frame, text="Status Koordynatora:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(status_frame, textvariable=self.server_status, fg="blue").pack(side=tk.LEFT, padx=10)

        # Główny kontener na tabele
        main_frame = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # TABELA 1: Węzły (Nodes)
        nodes_frame = tk.LabelFrame(main_frame, text="Aktywne Węzły (Workery)")
        main_frame.add(nodes_frame, minsize=300)
        
        columns_nodes = ("name", "cpu", "ram")
        self.tree_nodes = ttk.Treeview(nodes_frame, columns=columns_nodes, show="headings")
        self.tree_nodes.heading("name", text="Nazwa")
        self.tree_nodes.heading("cpu", text="Procesor (CPU)")
        self.tree_nodes.heading("ram", text="RAM (GB)")
        self.tree_nodes.column("name", width=120)
        self.tree_nodes.column("cpu", width=150)
        self.tree_nodes.column("ram", width=70)
        self.tree_nodes.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # TABELA 2: Zadania (Tasks)
        tasks_frame = tk.LabelFrame(main_frame, text="Kolejka Zadań")
        main_frame.add(tasks_frame, minsize=400)

        columns_tasks = ("id", "name", "status", "worker")
        self.tree_tasks = ttk.Treeview(tasks_frame, columns=columns_tasks, show="headings")
        self.tree_tasks.heading("id", text="ID")
        self.tree_tasks.heading("name", text="Zadanie")
        self.tree_tasks.heading("status", text="Status")
        self.tree_tasks.heading("worker", text="Wykonawca")
        self.tree_tasks.column("id", width=60)
        self.tree_tasks.column("name", width=120)
        self.tree_tasks.column("status", width=80)
        self.tree_tasks.column("worker", width=120)
        self.tree_tasks.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Dolny pasek do dodawania zadań
        cmd_frame = tk.LabelFrame(self.root, text="Zleć nowe zadanie", pady=10)
        cmd_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(cmd_frame, text="Komenda:").pack(side=tk.LEFT, padx=5)
        self.cmd_entry = tk.Entry(cmd_frame, width=50)
        self.cmd_entry.pack(side=tk.LEFT, padx=5)
        self.cmd_entry.insert(0, "python fib.py 30") # Domyślna komenda

        btn_submit = tk.Button(cmd_frame, text="Wyślij do sieci", bg="green", fg="white", command=self.submit_task)
        btn_submit.pack(side=tk.LEFT, padx=10)

    def submit_task(self):
        cmd = self.cmd_entry.get()
        if not cmd:
            messagebox.showwarning("Błąd", "Wpisz komendę!")
            return
            
        payload = {"command": cmd, "name": "GUI-Task", "submitter": "Dashboard"}
        try:
            r = requests.post(f"{PP_URL}/task", json=payload, headers=get_headers(), timeout=3)
            if r.status_code == 201:
                self.cmd_entry.delete(0, tk.END)
                self.refresh_data() # Wymuś odświeżenie natychmiast
            else:
                messagebox.showerror("Błąd serwera", r.text)
        except Exception as e:
            messagebox.showerror("Błąd komunikacji", str(e))

    def refresh_data(self):
        """Pobiera dane w tle co 2 sekundy, tworząc efekt 'na żywo'."""
        try:
            # Sprawdzanie węzłów
            r_nodes = requests.get(f"{PP_URL}/nodes", headers=get_headers(), timeout=2)
            if r_nodes.status_code == 200:
                self.server_status.set(f"Połączono z {PP_URL} (OK)")
                
                # Aktualizacja tabeli węzłów
                self.tree_nodes.delete(*self.tree_nodes.get_children())
                for n in r_nodes.json():
                    info = n.get("info", {})
                    self.tree_nodes.insert("", tk.END, values=(n.get("name"), info.get("cpu", "N/A"), info.get("ram_gb", "N/A")))

            # Sprawdzanie zadań
            r_tasks = requests.get(f"{PP_URL}/tasks", headers=get_headers(), timeout=2)
            if r_tasks.status_code == 200:
                self.tree_tasks.delete(*self.tree_tasks.get_children())
                for t in reversed(r_tasks.json()): # Odwracamy, by nowe były na górze
                    self.tree_tasks.insert("", tk.END, values=(t.get("id")[:6], t.get("name"), t.get("status"), t.get("assigned_to") or "-"))

        except requests.exceptions.RequestException:
            self.server_status.set("Brak połączenia z koordynatorem!")
            
        # Zapętl funkcję co 2000 ms (2 sekundy)
        self.root.after(2000, self.refresh_data)

if __name__ == "__main__":
    root = tk.Tk()
    app = PatientPredatorGUI(root)
    root.mainloop()