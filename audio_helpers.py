import tempfile
from collections import deque
from concurrent import futures
from threading import Event

import librosa
import pyrubberband
import simpleaudio as sa
import soundfile as sf
from nltk.tokenize import sent_tokenize
from pydub import AudioSegment
from simpleaudio import WaveObject
from tqdm.auto import tqdm
from piper import PiperVoice
import wave


class AudioCache:
    def __init__(self, max_size: int):
        self.cache = deque(maxlen=max_size)

    def get(self, text: str, speed_factor: float):
        for cached_text, cached_speed, audio_file_path in self.cache:
            if cached_text == text and cached_speed == speed_factor:
                print("Hit cache")
                return audio_file_path
        return None

    def add(self, text: str, speed_factor: float, audio_file_path: str):
        self.cache.append((text, speed_factor, audio_file_path))


audio_cache = AudioCache(max_size=20)


def tts_piper(
    text: str,
    speaker: str,
    audio_file_path: str,
    speed_factor: float = 1,
) -> None:
    with wave.open(audio_file_path, "wb") as wav_file:
        # Set the WAV file parameters
        voice = PiperVoice.load(speaker)
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(voice.config.sample_rate)  # Use the model's sample rate

        # Generate audio
        voice.synthesize(
            text=text,
            wav_file=wav_file,
            length_scale=1.0 / speed_factor,
            sentence_silence=0.3,
        )


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
    speaker: str,
) -> WaveObject:
    cached_audio_path = audio_cache.get(text_chunk, speed_factor)
    if cached_audio_path:
        audio_file_path = cached_audio_path
    else:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".wav", mode="wb"
        ) as temp_file:
            audio_file_path = temp_file.name

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".mp3", mode="wb"
            ) as temp_mp3_file:
                temp_mp3_file_path = temp_mp3_file.name
                tts_piper(text_chunk, speaker, temp_mp3_file_path, speed_factor)

                audio_segment = AudioSegment.from_file(temp_mp3_file_path)
                audio_segment.export(audio_file_path, format="wav")

            audio_cache.add(text_chunk, speed_factor, audio_file_path)

    wave_obj = sa.WaveObject.from_wave_file(audio_file_path)
    return wave_obj


def make_sentences(text: str) -> list[str]:
    remove_chars = [[";", " "], [".,", " "]]
    for char in remove_chars:
        text = text.replace(char[0], char[1])

    text_chunks = sent_tokenize(text)
    for rm in ["\n", "\r", "\t", ".", " "]:
        if rm in text_chunks:
            text_chunks.remove(rm)

    text_chunks = [chunk.strip() for chunk in text_chunks]

    return text_chunks


def async_audio_generation(
    stop_event: Event,
    text: str,
    speaker: str,
    speed_factor: float = 1,
) -> None:
    """
    Asynchronously generates and plays audio from text.

    Args:
        text: The text to be converted to speech.
        speed_factor: Speed factor for the audio.
        stop_event: An event to signal stopping the audio generation.
    """
    text_chunks = make_sentences(text)

    print(text_chunks)

    word_count = 0
    for chunk in text_chunks:
        word_count += len(chunk.split())

    progress_bar = tqdm(total=word_count, desc="Playing audio")

    with futures.ThreadPoolExecutor(max_workers=1) as audio_gen_executor:
        # Store futures with their index and associated text chunk
        indexed_futures = {
            index: (
                audio_gen_executor.submit(
                    create_audio_segment,
                    chunk,
                    speed_factor,
                    speaker,
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
            print(len(chunk_text))
            play_obj = audio_obj.play()

            while play_obj.is_playing():
                if stop_event.is_set():
                    play_obj.stop()
                    progress_bar.update(word_count - index)
                    progress_bar.refresh()
                    progress_bar.close()
                    break
            progress_bar.update(len(chunk_text.split()))
        progress_bar.close()
