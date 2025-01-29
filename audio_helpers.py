import logging
import tempfile
import time
import wave
from collections import deque
from concurrent import futures
from threading import Event

import simpleaudio as sa
import soundfile as sf
from nltk.tokenize import sent_tokenize
from piper import PiperVoice
from simpleaudio import WaveObject
from tqdm.auto import tqdm

from text_cleaning import combined_text_cleaning

logging.getLogger("phonemizer").setLevel(logging.ERROR)

FAILED_TO_COPY_TEXT = "Sorry, I failed to copy that text"

STATIC_CACHE_STRING = [FAILED_TO_COPY_TEXT]


class AudioCache:
    def __init__(self, max_size: int):
        self.cache = deque(maxlen=max_size)
        self.static_cache = []

    def get(self, text: str, speed_factor: float):
        for cache_type in [self.cache, self.static_cache]:
            for cached_text, cached_speed, audio_file_path in cache_type:
                if cached_text == text and cached_speed == speed_factor:
                    logging.info(f"Cache hit for {text}")
                    return audio_file_path
        return None

    def add(self, text: str, speed_factor: float, audio_file_path: str, static=False):
        if static:
            logging.info("Adding text to static cache")
            self.static_cache.append((text, speed_factor, audio_file_path))
        else:
            logging.info("Adding text to cache")
            self.cache.append((text, speed_factor, audio_file_path))


audio_cache = AudioCache(max_size=20)


def tts_piper(
    text: str,
    speaker: str,
    audio_file_path: str,
    speed_factor: float = 1,
) -> None:
    with wave.open(audio_file_path, "wb") as wav_file:

        voice = PiperVoice.load(speaker)
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(voice.config.sample_rate)

        voice.synthesize(
            text=text,
            wav_file=wav_file,
            length_scale=1.0 / speed_factor,
            sentence_silence=0.3,
        )


def tts_kokoro(
    text: str,
    speaker: str,
    audio_file_path: str,
    speed_factor: float = 1,
    engine=None,
) -> None:
    if engine is None:
        raise ValueError("Kokoro engine is not initialized")
    samples, sample_rate = engine.create(
        text,
        voice=speaker,
        speed=speed_factor,
        lang="en-us",
    )
    sf.write(audio_file_path, samples, sample_rate)


def create_audio_segment(
    stop_event: Event,
    text_chunk: str,
    speed_factor: float,
    speaker: str,
    tts_provider: str,
    engine,
    audio_generation_bar: tqdm,
) -> WaveObject | None:

    if stop_event.is_set():
        return
    cached_audio_path = audio_cache.get(text_chunk, speed_factor)
    if cached_audio_path:
        audio_file_path = cached_audio_path
    else:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".wav", mode="wb"
        ) as temp_file:
            audio_file_path = temp_file.name

            if tts_provider == "piper":
                tts_piper(text_chunk, speaker, audio_file_path, speed_factor)
            elif tts_provider == "kokoro":
                tts_kokoro(text_chunk, speaker, audio_file_path, speed_factor, engine)

            if text_chunk in STATIC_CACHE_STRING:
                audio_cache.add(text_chunk, speed_factor, audio_file_path, static=True)
            else:
                audio_cache.add(text_chunk, speed_factor, audio_file_path)
    if stop_event.is_set():
        return

    wave_obj = sa.WaveObject.from_wave_file(audio_file_path)
    audio_generation_bar.update(1)
    audio_generation_bar.refresh()
    return wave_obj


def make_sentences(text: str) -> list[str]:

    text_chunks = sent_tokenize(text)
    for rm in ["\r", "\t", ".", " "]:
        if rm in text_chunks:
            text_chunks.remove(rm)

    text_chunks = [chunk.strip() for chunk in text_chunks]

    return text_chunks


def read_sentences(
    text_chunks: list[str],
    indexed_futures: dict,
    stop_event: Event,
    sentence_pause: float,
):
    word_count = 0
    for chunk in text_chunks:
        word_count += len(chunk.split())

    progress_bar = tqdm(
        total=word_count, desc="Playing audio", unit=" words", leave=False, position=1
    )

    current_sentence = tqdm(total=0, bar_format="{desc}", position=2, leave=False)

    for index in sorted(indexed_futures.keys()):

        future, chunk_text = indexed_futures[index]
        logging.info(chunk_text)
        current_sentence.set_description_str(chunk_text)
        current_sentence.refresh()

        if stop_event.is_set():
            break

        audio_obj = future.result()

        if audio_obj is None:
            break

        if stop_event.is_set():
            break

        if index > 0:
            time.sleep(sentence_pause)

        play_obj = audio_obj.play()

        while play_obj.is_playing():
            if stop_event.is_set():
                play_obj.stop()
                break
        progress_bar.update(len(chunk_text.split()))

    # Clean up progress bars
    progress_bar.update(word_count - index)
    progress_bar.refresh()
    progress_bar.close()

    current_sentence.refresh()
    current_sentence.close()


def async_audio_generation(
    stop_event: Event,
    text: str,
    speaker: str,
    speed_factor: float = 1,
    tts_provider: str = "piper",
    engine=None,
    sentence_pause: float = 0.3,
) -> None:
    """
    Asynchronously generates and plays audio from text.

    Args:
        text: The text to be converted to speech.
        speed_factor: Speed factor for the audio.
        stop_event: An event to signal stopping the audio generation.
    """
    # Remove unwanted characters
    logging.info(f"Input text: {text}")
    text = combined_text_cleaning(text)
    logging.info(f"Cleaned text: {text}")

    text_chunks = make_sentences(text)

    logging.info(f"All input text: {text_chunks}")

    audio_generation_bar = tqdm(
        total=len(text_chunks),
        position=0,
        leave=False,
        desc="Generating audio",
        unit=" sentences",
    )

    with futures.ThreadPoolExecutor(max_workers=1) as audio_gen_executor:
        # Store futures with their index and associated text chunk
        indexed_futures = {
            index: (
                audio_gen_executor.submit(
                    create_audio_segment,
                    stop_event,
                    chunk,
                    speed_factor,
                    speaker,
                    tts_provider,
                    engine,
                    audio_generation_bar,
                ),
                chunk,
            )
            for index, chunk in enumerate(text_chunks)
        }

        read_sentences(text_chunks, indexed_futures, stop_event, sentence_pause)

    audio_generation_bar.update(len(text_chunks) - audio_generation_bar.n)
    audio_generation_bar.refresh()
    audio_generation_bar.close()
