import unittest
import os
from device import Device

class TestDeviceModule(unittest.TestCase):
    def setUp(self):
        """Przygotowanie instancji urządzenia przed każdym testem."""
        self.test_device = Device(name="TestNode01", device_type="worker")

    def test_initial_state(self):
        """Sprawdza, czy domyślne wartości po utworzeniu obiektu są poprawne."""
        self.assertEqual(self.test_device.name, "TestNode01")
        self.assertEqual(self.test_device.device_type, "worker")
        self.assertEqual(self.test_device.status, "offline")
        self.assertEqual(self.test_device.disk_usage_percent, 0.0)
        self.assertEqual(self.test_device.running_processes, 0)

    def test_static_info_fetching(self):
        """Sprawdza, czy funkcja fetch_info poprawnie zbiera dane o sprzęcie."""
        self.test_device.fetch_info()
        
        # Sprawdzamy czy podstawowe pola nie są puste lub domyślne
        self.assertNotEqual(self.test_device.os, "unknown")
        self.assertGreater(self.test_device.ram_gb, 0.0)
        self.assertGreater(self.test_device.storage_gb, 0.0)
        self.assertTrue(len(self.test_device.ip_address) > 0)

    def test_dynamic_status_updating(self):
        """Sprawdza, czy funkcja update_status poprawnie odświeża metryki."""
        self.test_device.update_status()
        
        # Po aktualizacji status powinien zmienić się na online
        self.assertEqual(self.test_device.status, "online")
        self.assertIsNotNone(self.test_device.last_seen)
        
        # Sprawdzamy, czy Twoje nowe metryki poprawnie zbierają dane
        self.assertGreaterEqual(self.test_device.disk_usage_percent, 0.0)
        self.assertGreater(self.test_device.running_processes, 0)
        self.assertGreaterEqual(self.test_device.uptime_seconds, 0)

    def test_string_representation(self):
        """Sprawdza, czy rzutowanie obiektu na tekst działa poprawnie."""
        self.assertEqual(str(self.test_device), "worker named TestNode01")

if __name__ == "__main__":
    unittest.main()