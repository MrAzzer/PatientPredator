import device

def main():
    my_device = device.Device(name="My Computer", device_type="PC")
    my_device.fetch_info()
    my_device.update_status()
    my_device.display_info()
    
if __name__ == "__main__":
    main()