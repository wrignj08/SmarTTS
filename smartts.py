import json
import threading
import time
from pathlib import Path
from threading import Event
from typing import Union

import emoji
import pyautogui
import pyperclip
from pynput.keyboard import Key, KeyCode, Listener

from audio_helpers import async_audio_generation


def copy_selected_text() -> str:
    """
    Copies the currently selected text to the clipboard.

    Returns:
        The text copied to the clipboard.
    """
    current_clipboard = pyperclip.paste()
    pyperclip.copy("")
    time.sleep(0.03)
    # Determine the key combination based on the OS
    pyautogui.hotkey("ctrl", "c", interval=0.1)

    # time.sleep(0.3)
    for i in range(2):
        clip_board = pyperclip.paste()
        if clip_board != "":
            # refill the clipboard with the original content
            pyperclip.copy(current_clipboard)
            return clip_board
        time.sleep(0.1)
    pyperclip.copy(current_clipboard)
    return ""


def check_inputs(speed_factor: float, speaker: str) -> None:
    print("Using Piper voice:")
    assert (Path.cwd() / speaker).exists(), f"Speaker file {speaker} does not exist"
    print(f"Using voice {speaker}")

    if speed_factor <= 0:
        raise ValueError("speed_factor must be greater than 0")
    else:
        print(f"Using speed factor {speed_factor}")


class AudioController:
    """
    Controller for managing the audio generation and playback.
    """

    def __init__(
        self,
        speaker="en_en_US_joe_medium_en_US-joe-medium.onnx",
        speed=1.0,
    ):
        self.speaker = speaker
        self.speed = speed
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

        reading_thread = threading.Thread(
            target=async_audio_generation,
            args=(
                stop_audio_event,
                selected_text,
                self.speaker,
                self.speed,
            ),
        )
        reading_thread.start()
        return reading_thread


if __name__ == "__main__":
    with open("config.json", "r") as file:
        settings = json.load(file)

    speed = settings.get("speed", 1.0)
    speaker = settings.get("speaker", "en_en_US_joe_medium_en_US-joe-medium.onnx")
    check_inputs(speed, speaker)

    audio_controller = AudioController(speaker=speaker, speed=speed)

    with Listener(on_press=audio_controller.start_stopper) as listener:
        listener.join()
