import os
import time
import requests

# Konfiguracja połączenia z koordynatorem
PP_URL = os.environ.get("PP_COORDINATOR", "http://localhost:4200").rstrip("/")
PP_TOKEN = os.environ.get("PP_TOKEN", "changeme")

def send_test_task(task_index, fib_number):
    """Wysyła pojedyncze zadanie obliczeniowe do koordynatora."""
    headers = {"X-Token": PP_TOKEN}
    payload = {
        # Wykorzystujemy istniejący w projekcie plik fib.py do obciążenia procesora
        "command": f"python fib.py {fib_number}",
        "name": f"Stress-Fib-{task_index}",
        "submitter": "StressTester-Bot"
    }
    
    try:
        r = requests.post(f"{PP_URL}/task", json=payload, headers=headers, timeout=5)
        if r.status_code == 201:
            print(f"[+] [Zadanie {task_index}] Pomyślnie dodano do kolejki (Fibonacci: {fib_number})")
            return True
        else:
            print(f"[-] [Zadanie {task_index}] Koordynator zwrócił błąd {r.status_code}: {r.text}")
            return False
    except Exception as e:
        print(f"[-] [Zadanie {task_index}] Brak połączenia z serwerem: {e}")
        return False

def main():
    print("=" * 60)
    print("   PatientPredator - Generator Obciążenia i Testów Skalowalności   ")
    print("=" * 60)
    print(f"Cel testu (Koordynator): {PP_URL}\n")
    
    try:
        num_tasks = int(input("Ile zadań chcesz wygenerować na raz? (domyślnie 5): ") or 5)
        fib_val = int(input("Jaki argument przekazać do fib.py? (np. 35 dla dużego obciążenia): ") or 35)
    except ValueError:
        print("[-] Podano nieprawidłową liczbę. Przerywam.")
        return

    print(f"\n[!] Uruchamiam test: Wysyłam {num_tasks} zadań obliczeniowych...")
    print("-" * 60)
    
    start_time = time.time()
    successful_dispatches = 0

    for i in range(1, num_tasks + 1):
        if send_test_task(i, fib_val):
            successful_dispatches += 1
        # Minimalny odstęp, żeby nie zapchać gniazd sieciowych w ułamku sekundy
        time.sleep(0.2)
        
    end_time = time.time()
    
    print("-" * 60)
    print(f"[+] Test zakończony.")
    print(f"[+] Wysłano pomyślnie: {successful_dispatches}/{num_tasks} zadań.")
    print(f"[+] Czas generowania paczki: {end_time - start_time:.2f} sekund.")
    print("[i] Możesz teraz odpalić 'python cli.py tasks', aby zobaczyć, jak workery je rozbierają.")
    print("=" * 60)

if __name__ == "__main__":
    main()