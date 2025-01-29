import argparse
import json
import logging
import threading
import time
from pathlib import Path
from threading import Event
from typing import Union

import pyautogui
import pyperclip
from kokoro_onnx import Kokoro
from pynput.keyboard import Key, KeyCode, Listener
from tqdm.auto import tqdm

from audio_helpers import FAILED_TO_COPY_TEXT, async_audio_generation


def copy_selected_text() -> str:
    """
    Copies the currently selected text to the clipboard.

    Returns:
        The text copied to the clipboard.
    """
    # grab the current clipboard content
    current_clipboard = pyperclip.paste()
    # clear the clipboard
    empty_clipboard = ""
    pyperclip.copy(empty_clipboard)
    time.sleep(0.03)
    # copy the selected text to the clipboard
    pyautogui.hotkey("ctrl", "c", interval=0.05)
    # wait for the clipboard to be filled
    for i in range(2):
        clip_board = pyperclip.paste()
        if clip_board != empty_clipboard:
            # refill the clipboard with the original content
            pyperclip.copy(current_clipboard)
            return clip_board
        time.sleep(0.1)
    # refill the clipboard with the original content
    pyperclip.copy(current_clipboard)
    return FAILED_TO_COPY_TEXT


def check_inputs(
    speed_factor: float, speaker: str, tts_provider: str, sentence_pause: float
) -> None:
    if tts_provider not in ["piper", "kokoro"]:
        raise ValueError("tts_provider must be either 'piper' or 'kokoro'")
    logging.info(f"Using {tts_provider} TTS provider")

    if tts_provider == "piper":
        assert (Path.cwd() / speaker).exists(), f"Speaker file {speaker} does not exist"

    else:
        assert (
            speaker in json.load(open("voices.json")).keys()
        ), f"Speaker {speaker} not found"
        logging.info(
            f'Other speakers available: {", ".join(json.load(open("voices.json")).keys())}'
        )

    logging.info(f"Using speaker {speaker}")

    if sentence_pause < 0:
        raise ValueError("sentence_pause must be greater than or equal to 0")

    logging.info(f"Using sentence pause {sentence_pause}")

    if speed_factor <= 0:
        raise ValueError("speed_factor must be greater than 0")
    else:
        logging.info(f"Using speed factor {speed_factor}")


class AudioController:
    """
    Controller for managing the audio generation and playback.
    """

    def __init__(
        self,
        speaker="en_en_US_joe_medium_en_US-joe-medium.onnx",
        speed=1.0,
        tts_provider="piper",
        engine=None,
        sentence_pause=0.3,
    ):
        self.speaker = speaker
        self.speed = speed
        self.tts_provider = tts_provider
        self.engine = engine
        self.sentence_pause = sentence_pause
        self.reading_thread = threading.Thread()
        self.stop_audio_event = Event()

    def start_stopper(self, key: Union[Key, KeyCode, None]) -> None:
        """
        Callback function for the keyboard listener to stop or start audio.

        Args:
            key: The key pressed, which can be of type Key, KeyCode, or None.
        """
        key_code = getattr(key, "vk", None)
        copy_then_read_key = 269025093
        read_from_clipboard_key = 269025094
        if key_code not in [copy_then_read_key, read_from_clipboard_key]:
            return

        from_clipboard = key_code == read_from_clipboard_key

        if self.reading_thread.is_alive():
            logging.info("Stopping audio")
            self.stop_audio_event.set()
            self.reading_thread.join()
            self.stop_audio_event.clear()

        else:
            logging.info("Starting audio")
            self.reading_thread = self.start_reading(
                self.stop_audio_event, from_clipboard
            )

    def start_reading(
        self, stop_audio_event: Event, from_clipboard: bool = False
    ) -> threading.Thread:
        """
        Starts a new thread for reading aloud the selected text.

        Args:
            stop_audio_event: An event to signal stopping the audio generation.

        Returns:
            The thread that was started for reading.
        """
        if from_clipboard:
            selected_text = pyperclip.paste()
        else:
            selected_text = copy_selected_text()

        reading_thread = threading.Thread(
            target=async_audio_generation,
            args=(
                stop_audio_event,
                selected_text,
                self.speaker,
                self.speed,
                self.tts_provider,
                self.engine,
            ),
        )
        reading_thread.start()
        return reading_thread


def setup_logging(show_info: bool):
    """Configure logging based on verbose flag"""
    if show_info:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        logging.basicConfig(
            level=logging.WARNING  # Only show warnings and errors by default
        )


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Text-to-Speech Controller")
    parser.add_argument("--verbose", action="store_true", help="Show info logs")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("Starting application")

    tqdm_setup_bar = tqdm(total=2, position=0, leave=True, desc="Loading config")
    with open("config.json", "r") as file:
        settings = json.load(file)

    speed = settings.get("speed", 1.0)
    speaker = settings.get("speaker", "en_en_US_joe_medium_en_US-joe-medium.onnx")
    tts_provider = settings.get("tts_provider", "piper")
    sentence_pause = settings.get("sentence_pause", 0.3)

    check_inputs(speed, speaker, tts_provider, sentence_pause)

    if tts_provider == "kokoro":
        engine = Kokoro("kokoro-v0_19.onnx", "voices.json")
    else:
        engine = None
    tqdm_setup_bar.update(1)
    tqdm_setup_bar.set_description("Setting up audio controller")

    audio_controller = AudioController(
        speaker=speaker,
        speed=speed,
        tts_provider=tts_provider,
        engine=engine,
        sentence_pause=sentence_pause,
    )

    tqdm_setup_bar.update(1)
    tqdm_setup_bar.set_description("Ready to read")
    tqdm_setup_bar.refresh()
    tqdm_setup_bar.close()

    with Listener(on_press=audio_controller.start_stopper) as listener:
        listener.join()
