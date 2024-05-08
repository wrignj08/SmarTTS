import json
import threading
import time
from pathlib import Path
from pprint import pprint
from threading import Event
from typing import Dict, Union

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


def parse_tts_file(
    file_path: Path = Path("edge_voices.txt"),
) -> Dict[str, Dict[str, str]]:
    with open(file_path, "r") as file:
        lines = file.readlines()

    tts_dict = {}
    current_entry = {}

    for line in lines:
        line = line.strip()
        if line:
            key, value = line.split(": ", 1)
            if key == "VoiceTag":
                # Convert string representation of dictionary to actual dictionary
                value = eval(value)
            current_entry[key] = value
        else:
            # Empty line indicates end of current entry
            if current_entry:
                short_name = current_entry.get("ShortName")
                tts_dict[short_name] = current_entry
                current_entry = {}

    # Add the last entry if file does not end with a newline
    if current_entry:
        short_name = current_entry.get("ShortName")
        tts_dict[short_name] = current_entry
    return tts_dict


def check_inputs(speed_factor: float, tts_provider: str, speaker: str) -> None:
    if tts_provider not in ["openai", "edge"]:
        raise ValueError("tts_provider must be either openai or edge")
    if tts_provider == "openai":
        if speaker not in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
            raise ValueError(
                "speaker must be one of alloy, echo, fable, onyx, nova, or shimmer"
            )
        else:
            pprint("Using OpenAI voice:")
            pprint(f"Using voice {speaker}")

    if tts_provider == "edge":
        voices = parse_tts_file()
        try:
            voice = voices[speaker]
            pprint("Using Edge voice:")
            pprint(f"Using voice {voice}")
        except KeyError:
            raise ValueError(f"speaker must be one of {list(voices.keys())}")

    if speed_factor <= 0:
        raise ValueError("speed_factor must be greater than 0")
    else:
        pprint(f"Using speed factor {speed_factor}")


class AudioController:
    """
    Controller for managing the audio generation and playback.
    tts_provider: The text-to-speech provider to use. openai or edge
    openai speakers: "alloy", "echo", "fable", "onyx", "nova", "shimmer"
    edge speakers: 'af-ZA-AdriNeural', 'af-ZA-WillemNeural', 'sq-AL-AnilaNeural', 'sq-AL-IlirNeural', 'am-ET-AmehaNeural', 'am-ET-MekdesNeural', 'ar-DZ-AminaNeural', 'ar-DZ-IsmaelNeural', 'ar-BH-AliNeural', 'ar-BH-LailaNeural', 'ar-EG-SalmaNeural', 'ar-EG-ShakirNeural', 'ar-IQ-BasselNeural', 'ar-IQ-RanaNeural', 'ar-JO-SanaNeural', 'ar-JO-TaimNeural', 'ar-KW-FahedNeural', 'ar-KW-NouraNeural', 'ar-LB-LaylaNeural', 'ar-LB-RamiNeural', 'ar-LY-ImanNeural', 'ar-LY-OmarNeural', 'ar-MA-JamalNeural', 'ar-MA-MounaNeural', 'ar-OM-AbdullahNeural', 'ar-OM-AyshaNeural', 'ar-QA-AmalNeural', 'ar-QA-MoazNeural', 'ar-SA-HamedNeural', 'ar-SA-ZariyahNeural', 'ar-SY-AmanyNeural', 'ar-SY-LaithNeural', 'ar-TN-HediNeural', 'ar-TN-ReemNeural', 'ar-AE-FatimaNeural', 'ar-AE-HamdanNeural', 'ar-YE-MaryamNeural', 'ar-YE-SalehNeural', 'az-AZ-BabekNeural', 'az-AZ-BanuNeural', 'bn-BD-NabanitaNeural', 'bn-BD-PradeepNeural', 'bn-IN-BashkarNeural', 'bn-IN-TanishaaNeural', 'bs-BA-GoranNeural', 'bs-BA-VesnaNeural', 'bg-BG-BorislavNeural', 'bg-BG-KalinaNeural', 'my-MM-NilarNeural', 'my-MM-ThihaNeural', 'ca-ES-EnricNeural', 'ca-ES-JoanaNeural', 'zh-HK-HiuGaaiNeural', 'zh-HK-HiuMaanNeural', 'zh-HK-WanLungNeural', 'zh-CN-XiaoxiaoNeural', 'zh-CN-XiaoyiNeural', 'zh-CN-YunjianNeural', 'zh-CN-YunxiNeural', 'zh-CN-YunxiaNeural', 'zh-CN-YunyangNeural', 'zh-CN-liaoning-XiaobeiNeural', 'zh-TW-HsiaoChenNeural', 'zh-TW-YunJheNeural', 'zh-TW-HsiaoYuNeural', 'zh-CN-shaanxi-XiaoniNeural', 'hr-HR-GabrijelaNeural', 'hr-HR-SreckoNeural', 'cs-CZ-AntoninNeural', 'cs-CZ-VlastaNeural', 'da-DK-ChristelNeural', 'da-DK-JeppeNeural', 'nl-BE-ArnaudNeural', 'nl-BE-DenaNeural', 'nl-NL-ColetteNeural', 'nl-NL-FennaNeural', 'nl-NL-MaartenNeural', 'en-AU-NatashaNeural', 'en-AU-WilliamNeural', 'en-CA-ClaraNeural', 'en-CA-LiamNeural', 'en-HK-SamNeural', 'en-HK-YanNeural', 'en-IN-NeerjaNeural', 'en-IN-PrabhatNeural', 'en-IE-ConnorNeural', 'en-IE-EmilyNeural', 'en-KE-AsiliaNeural', 'en-KE-ChilembaNeural', 'en-NZ-MitchellNeural', 'en-NZ-MollyNeural', 'en-NG-AbeoNeural', 'en-NG-EzinneNeural', 'en-PH-JamesNeural', 'en-PH-RosaNeural', 'en-SG-LunaNeural', 'en-SG-WayneNeural', 'en-ZA-LeahNeural', 'en-ZA-LukeNeural', 'en-TZ-ElimuNeural', 'en-TZ-ImaniNeural', 'en-GB-LibbyNeural', 'en-GB-MaisieNeural', 'en-GB-RyanNeural', 'en-GB-SoniaNeural', 'en-GB-ThomasNeural', 'en-US-AriaNeural', 'en-US-AnaNeural', 'en-US-ChristopherNeural', 'en-US-EricNeural', 'en-US-GuyNeural', 'en-US-JennyNeural', 'en-US-MichelleNeural', 'en-US-RogerNeural', 'en-US-SteffanNeural', 'et-EE-AnuNeural', 'et-EE-KertNeural', 'fil-PH-AngeloNeural', 'fil-PH-BlessicaNeural', 'fi-FI-HarriNeural', 'fi-FI-NooraNeural', 'fr-BE-CharlineNeural', 'fr-BE-GerardNeural', 'fr-CA-AntoineNeural', 'fr-CA-JeanNeural', 'fr-CA-SylvieNeural', 'fr-FR-DeniseNeural', 'fr-FR-EloiseNeural', 'fr-FR-HenriNeural', 'fr-CH-ArianeNeural', 'fr-CH-FabriceNeural', 'gl-ES-RoiNeural', 'gl-ES-SabelaNeural', 'ka-GE-EkaNeural', 'ka-GE-GiorgiNeural', 'de-AT-IngridNeural', 'de-AT-JonasNeural', 'de-DE-AmalaNeural', 'de-DE-ConradNeural', 'de-DE-KatjaNeural', 'de-DE-KillianNeural', 'de-CH-JanNeural', 'de-CH-LeniNeural', 'el-GR-AthinaNeural', 'el-GR-NestorasNeural', 'gu-IN-DhwaniNeural', 'gu-IN-NiranjanNeural', 'he-IL-AvriNeural', 'he-IL-HilaNeural', 'hi-IN-MadhurNeural', 'hi-IN-SwaraNeural', 'hu-HU-NoemiNeural', 'hu-HU-TamasNeural', 'is-IS-GudrunNeural', 'is-IS-GunnarNeural', 'id-ID-ArdiNeural', 'id-ID-GadisNeural', 'ga-IE-ColmNeural', 'ga-IE-OrlaNeural', 'it-IT-DiegoNeural', 'it-IT-ElsaNeural', 'it-IT-IsabellaNeural', 'ja-JP-KeitaNeural', 'ja-JP-NanamiNeural', 'jv-ID-DimasNeural', 'jv-ID-SitiNeural', 'kn-IN-GaganNeural', 'kn-IN-SapnaNeural', 'kk-KZ-AigulNeural', 'kk-KZ-DauletNeural', 'km-KH-PisethNeural', 'km-KH-SreymomNeural', 'ko-KR-InJoonNeural', 'ko-KR-SunHiNeural', 'lo-LA-ChanthavongNeural', 'lo-LA-KeomanyNeural', 'lv-LV-EveritaNeural', 'lv-LV-NilsNeural', 'lt-LT-LeonasNeural', 'lt-LT-OnaNeural', 'mk-MK-AleksandarNeural', 'mk-MK-MarijaNeural', 'ms-MY-OsmanNeural', 'ms-MY-YasminNeural', 'ml-IN-MidhunNeural', 'ml-IN-SobhanaNeural', 'mt-MT-GraceNeural', 'mt-MT-JosephNeural', 'mr-IN-AarohiNeural', 'mr-IN-ManoharNeural', 'mn-MN-BataaNeural', 'mn-MN-YesuiNeural', 'ne-NP-HemkalaNeural', 'ne-NP-SagarNeural', 'nb-NO-FinnNeural', 'nb-NO-PernilleNeural', 'ps-AF-GulNawazNeural', 'ps-AF-LatifaNeural', 'fa-IR-DilaraNeural', 'fa-IR-FaridNeural', 'pl-PL-MarekNeural', 'pl-PL-ZofiaNeural', 'pt-BR-AntonioNeural', 'pt-BR-FranciscaNeural', 'pt-PT-DuarteNeural', 'pt-PT-RaquelNeural', 'ro-RO-AlinaNeural', 'ro-RO-EmilNeural', 'ru-RU-DmitryNeural', 'ru-RU-SvetlanaNeural', 'sr-RS-NicholasNeural', 'sr-RS-SophieNeural', 'si-LK-SameeraNeural', 'si-LK-ThiliniNeural', 'sk-SK-LukasNeural', 'sk-SK-ViktoriaNeural', 'sl-SI-PetraNeural', 'sl-SI-RokNeural', 'so-SO-MuuseNeural', 'so-SO-UbaxNeural', 'es-AR-ElenaNeural', 'es-AR-TomasNeural', 'es-BO-MarceloNeural', 'es-BO-SofiaNeural', 'es-CL-CatalinaNeural', 'es-CL-LorenzoNeural', 'es-CO-GonzaloNeural', 'es-CO-SalomeNeural', 'es-CR-JuanNeural', 'es-CR-MariaNeural', 'es-CU-BelkysNeural', 'es-CU-ManuelNeural', 'es-DO-EmilioNeural', 'es-DO-RamonaNeural', 'es-EC-AndreaNeural', 'es-EC-LuisNeural', 'es-SV-LorenaNeural', 'es-SV-RodrigoNeural', 'es-GQ-JavierNeural', 'es-GQ-TeresaNeural', 'es-GT-AndresNeural', 'es-GT-MartaNeural', 'es-HN-CarlosNeural', 'es-HN-KarlaNeural', 'es-MX-DaliaNeural', 'es-MX-JorgeNeural', 'es-MX-LorenzoEsCLNeural', 'es-NI-FedericoNeural', 'es-NI-YolandaNeural', 'es-PA-MargaritaNeural', 'es-PA-RobertoNeural', 'es-PY-MarioNeural', 'es-PY-TaniaNeural', 'es-PE-AlexNeural', 'es-PE-CamilaNeural', 'es-PR-KarinaNeural', 'es-PR-VictorNeural', 'es-ES-AlvaroNeural', 'es-ES-ElviraNeural', 'es-ES-ManuelEsCUNeural', 'es-US-AlonsoNeural', 'es-US-PalomaNeural', 'es-UY-MateoNeural', 'es-UY-ValentinaNeural', 'es-VE-PaolaNeural', 'es-VE-SebastianNeural', 'su-ID-JajangNeural', 'su-ID-TutiNeural', 'sw-KE-RafikiNeural', 'sw-KE-ZuriNeural', 'sw-TZ-DaudiNeural', 'sw-TZ-RehemaNeural', 'sv-SE-MattiasNeural', 'sv-SE-SofieNeural', 'ta-IN-PallaviNeural', 'ta-IN-ValluvarNeural', 'ta-MY-KaniNeural', 'ta-MY-SuryaNeural', 'ta-SG-AnbuNeural', 'ta-SG-VenbaNeural', 'ta-LK-KumarNeural', 'ta-LK-SaranyaNeural', 'te-IN-MohanNeural', 'te-IN-ShrutiNeural', 'th-TH-NiwatNeural', 'th-TH-PremwadeeNeural', 'tr-TR-AhmetNeural', 'tr-TR-EmelNeural', 'uk-UA-OstapNeural', 'uk-UA-PolinaNeural', 'ur-IN-GulNeural', 'ur-IN-SalmanNeural', 'ur-PK-AsadNeural', 'ur-PK-UzmaNeural', 'uz-UZ-MadinaNeural', 'uz-UZ-SardorNeural', 'vi-VN-HoaiMyNeural', 'vi-VN-NamMinhNeural', 'cy-GB-AledNeural', 'cy-GB-NiaNeural', 'zu-ZA-ThandoNeural', 'zu-ZA-ThembaNeural'

    """

    def __init__(
        self,
        tts_provider="edge",
        speaker="en-GB-SoniaNeural",
        speed=1.0,
    ):
        self.tts_provider = tts_provider
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
            # print("Stopping audio")
            self.stop_audio_event.set()
            self.reading_thread.join()
            self.stop_audio_event.clear()
        else:
            # print("Starting audio")
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
                self.tts_provider,
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
    tts_provider = settings.get("tts_provider", "edge")
    speaker = settings.get("speaker", "en-GB-SoniaNeural")
    check_inputs(speed, tts_provider, speaker)

    audio_controller = AudioController(
        tts_provider=tts_provider, speaker=speaker, speed=speed
    )

    with Listener(on_press=audio_controller.start_stopper) as listener:
        listener.join()
