#klasa reprezentująca urządzenie w systemie

class Device:
    def __init__(self, name, device_type):
        #nazwa
        self.name = name
        self.device_type = device_type
        
        #stan
        self.status = "offline"
        self.last_seen = None
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        
        #bebechy
        
        self.cpu_name = "jakis intel"
        self.ram_gb = 0
        self.storage_gb = 0
        
        
        

    def __str__(self):
        return f"{self.device_type} named {self.name}"
    
    
# funkcja pobierajace informacje o urzadzeniu

# funkcja aktualizujaca stan urzadzenia

# funkcja wyswietlajaca informacje o urzadzeniu


