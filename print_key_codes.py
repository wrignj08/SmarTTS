from pynput import keyboard

if __name__ == "__main__":

    def display_key_codes(key):
        key_code = getattr(key, "vk", None)
        print(f"Key code: {key_code}")
        print(f"Key: {key}")
        print(f"Key: {key.vk}")

    listener = keyboard.Listener(display_key_codes)
    listener.start()
    while True:
        pass
