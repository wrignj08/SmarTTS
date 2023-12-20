from threading import Event
import threading
import time
from typing import Union
from pynput.keyboard import Key, KeyCode, Listener
import pyperclip
import platform
import pyautogui
import emoji

from audio_helpers import async_audio_generation


def copy_selected_text() -> str:
    """
    Copies the currently selected text to the clipboard.

    Returns:
        The text copied to the clipboard.
    """
    os_name = platform.system()
    pyperclip.copy("")
    time.sleep(0.03)
    # Determine the key combination based on the OS
    if os_name == "Darwin":  # macOS
        pyautogui.hotkey("command", "c")
    else:  # Windows and Linux
        pyautogui.hotkey("ctrl", "c")

    time.sleep(0.3)
    for i in range(2):
        clip_board = pyperclip.paste()
        if clip_board != "":
            return clip_board
        time.sleep(0.1)
    return ""


class AudioController:
    """
    Controller for managing the audio generation and playback.
    """

    def __init__(self):
        self.reading_thread = threading.Thread()
        self.stop_audio_event = Event()

    def start_stopper(self, key: Union[Key, KeyCode, None]) -> None:
        """
        Callback function for the keyboard listener to stop or start audio.

        Args:
            key: The key pressed, which can be of type Key, KeyCode, or None.
        """
        key_code = getattr(key, "vk", None)
        if key_code != 269025093:  # Key.f9:
            return
        if self.reading_thread.is_alive():
            print("Stopping audio")
            self.stop_audio_event.set()
            self.reading_thread.join()
            self.stop_audio_event.clear()
        else:
            print("Starting audio")
            self.reading_thread = self.start_reading(self.stop_audio_event)

    def start_reading(self, stop_audio_event: Event) -> threading.Thread:
        """
        Starts a new thread for reading aloud the selected text.

        Args:
            stop_audio_event: An event to signal stopping the audio generation.

        Returns:
            The thread that was started for reading.
        """
        selected_text = copy_selected_text()
        # convert emojis to text
        selected_text = emoji.demojize(selected_text)
        selected_text = selected_text.replace(":", "")

        # print(f"Captured text: {selected_text}")
        reading_thread = threading.Thread(
            target=async_audio_generation,
            args=(selected_text, 2.0, stop_audio_event),
        )
        reading_thread.start()
        return reading_thread


if __name__ == "__main__":
    audio_controller = AudioController()

    with Listener(on_press=audio_controller.start_stopper) as listener:
        listener.join()
