import asyncio
import logging
import tempfile
import time
from collections import deque
from concurrent import futures
from threading import Event
from typing import Literal

import edge_tts
import librosa
import openai
import pyrubberband
import simpleaudio as sa
import soundfile as sf
from nltk.tokenize import sent_tokenize
from openai import OpenAI
from pydub import AudioSegment
from simpleaudio import WaveObject
from tqdm.auto import tqdm


class AudioCache:
    def __init__(self, max_size: int):
        self.cache = deque(maxlen=max_size)

    def get(self, text: str):
        for cached_text, audio_file_path in self.cache:
            if cached_text == text:
                return audio_file_path
        return None

    def add(self, text: str, audio_file_path: str):
        self.cache.append((text, audio_file_path))


audio_cache = AudioCache(max_size=20)


def tts_openai(
    text: str,
    speaker: str,
    use_hd: bool,
    audio_file_path: str,
) -> None:
    """
    Generates speech from text using OpenAI's TTS and saves it to a file.

    Args:
        text: The text to be converted to speech.
        audio_file_path: The file path where the audio will be saved.
    """
    if use_hd:
        model = "tts-1-hd"
    else:
        model = "tts-1"
    client = OpenAI()
    # Generate speech
    try:
        response = client.audio.speech.create(
            model=model,
            voice=speaker,  # type: ignore
            input=text,
        )
        response.stream_to_file(audio_file_path)
    except openai.RateLimitError as e:
        # This is a placeholder for OpenAI's specific error class; replace with the actual one
        logging.error(f"OpenAI TTS error: {e}")
        return
        # Here you can handle specific OpenAI errors differently
    except Exception as e:
        logging.error(f"Unexpected error in TTS processing: {e}")
        # This catches any other exceptions not specifically handled above


async def edge_tts_worker(text: str, speaker: str, output_file_path: str):
    attempts = 2  # Allows for the initial try and one retry
    communicate = edge_tts.Communicate(text, speaker)
    while attempts > 0:
        try:
            with open(output_file_path, "wb") as file:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        file.write(chunk["data"])
            break  # Exit the loop if the operation is successful
        except asyncio.TimeoutError:
            attempts -= 1  # Decrement the number of attempts left
            if attempts == 0:
                logging.error(
                    "Failed to complete the operation after a retry. A timeout occurred."
                )
            else:
                logging.info("Timeout occurred, retrying...")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            break  # Exit the loop if a non-timeout error occurs

    if attempts == 0:
        logging.error(
            "Failed to complete the operation after a retry. A timeout occurred."
        )


async def tts_edge(
    text: str,
    speaker: str,
    output_file_path: str,
):
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If the loop is running, create a new task and await its completion
        task = loop.create_task(edge_tts_worker(text, speaker, output_file_path))
        await task
    else:
        # If the loop is not running, use run_until_complete
        loop.run_until_complete(edge_tts_worker(text, speaker, output_file_path))


def adjust_audio_speed(speed_factor: float, audio_file: str) -> None:
    """
    Adjusts the speed of an audio file.

    Args:
        speed_factor: Factor by which to adjust the speed.
        audio_file: Path to the audio file to be adjusted.
    """
    y, sr = librosa.load(audio_file, sr=None)
    y_stretched = pyrubberband.time_stretch(y, sr, speed_factor)
    sf.write(audio_file, y_stretched, sr, format="wav")


def create_audio_segment(
    text_chunk: str,
    speed_factor: float,
    use_hd: bool,
    speaker: str,
    tts_provider: Literal["openai", "edge"] = "edge",
) -> WaveObject:
    """
    Creates an audio segment from a text chunk with adjusted speed.

    Args:
        text_chunk: Text chunk to be converted to audio.
        speed_factor: Speed adjustment factor.

    Returns:
        A WaveObject representing the audio segment.
    """
    cached_audio_path = audio_cache.get(text_chunk)
    if cached_audio_path:
        print("Using cached audio")
        audio_file_path = cached_audio_path
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".mp3", mode="wb"
    ) as temp_file:
        audio_file_path = temp_file.name

        if tts_provider == "edge":
            asyncio.run(tts_edge(text_chunk, speaker, audio_file_path))

        else:
            tts_openai(text_chunk, speaker, use_hd, audio_file_path)

        audio_cache.add(text_chunk, audio_file_path)

        audio_segment = AudioSegment.from_file(str(audio_file_path))

        try:
            audio_segment.export(str(audio_file_path), format="wav")

            if speed_factor > 1:
                adjust_audio_speed(speed_factor, str(audio_file_path))

        except Exception as e:
            print(f"Error in audio manipulation: {e}")
            print("Audio too small to trim or speed up")

        wave_obj = sa.WaveObject.from_wave_file(str(audio_file_path))
        return wave_obj


def async_audio_generation(
    stop_event: Event,
    text: str,
    tts_provider: Literal["openai", "edge"] = "edge",
    speaker: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "alloy",
    speed_factor: float = 1,
) -> None:
    """
    Asynchronously generates and plays audio from text.

    Args:
        text: The text to be converted to speech.
        speed_factor: Speed factor for the audio.
        stop_event: An event to signal stopping the audio generation.
    """
    text_chunks = sent_tokenize(text)
    progress_bar = tqdm(total=len(text_chunks), desc="Playing audio")

    with futures.ThreadPoolExecutor(max_workers=1) as audio_gen_executor:
        # Store futures with their index and associated text chunk
        indexed_futures = {
            index: (
                audio_gen_executor.submit(
                    create_audio_segment,
                    chunk,
                    speed_factor,
                    False,
                    speaker,
                    tts_provider,
                ),
                chunk,
            )
            for index, chunk in enumerate(text_chunks)
        }

        # Sort futures based on index before playback
        for index in sorted(indexed_futures.keys()):
            if stop_event.is_set():
                break

            future, chunk_text = indexed_futures[index]
            audio_obj = future.result()

            print(chunk_text)
            play_obj = audio_obj.play()

            while play_obj.is_playing():
                if stop_event.is_set():
                    play_obj.stop()
                    progress_bar.update(len(text_chunks) - index)
                    progress_bar.close()
                    break
                time.sleep(0.1)
            progress_bar.update(1)
        progress_bar.close()
