import hashlib
from dataclasses import dataclass
from functools import cached_property
from importlib.metadata import version
from pathlib import Path

import numpy as np
import soundfile as sf

from duolingo_anki.cards import spoken_text

MODEL = "supertonic-3"
LANGUAGE = "nl"
VOICES = ("F1", "M1")


def digest(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def voice_for(dutch: str) -> str:
    return VOICES[digest(dutch)[0] % len(VOICES)]


def file_name(text: str, voice: str) -> str:
    return f"nl-{digest(f'{voice}:{text}').hex()[:16]}.mp3"


@dataclass(frozen=True)
class Clip:
    text: str
    file: str


class Speaker:
    name = f"supertonic {version('supertonic')} ({MODEL})"

    @cached_property
    def engine(self):
        from supertonic import TTS

        return TTS(model=MODEL)

    @cached_property
    def supported(self) -> set[str]:
        return self.engine.model.text_processor.supported_character_set

    def speakable(self, text: str) -> str:
        return "".join(character for character in text if character in self.supported or character.isspace())

    @cached_property
    def styles(self) -> dict:
        return {voice: self.engine.get_voice_style(voice_name=voice) for voice in VOICES}

    def speak(self, text: str, voice: str, directory: Path) -> Clip:
        clip = Clip(text, file_name(text, voice))
        path = directory / clip.file
        if not path.exists():
            np.random.seed(int.from_bytes(digest(text)[:4]))
            samples, _ = self.engine.synthesize(self.speakable(text), voice_style=self.styles[voice], lang=LANGUAGE)
            sf.write(path, np.asarray(samples).reshape(-1), self.engine.sample_rate, format="MP3")
        return clip


def build_audio(entries: list[dict], displayed: dict[str, str], directory: Path, speaker: Speaker) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    for entry in entries:
        voice = voice_for(entry["dutch"])
        word = spoken_text(displayed[entry["dutch"]])
        manifest.append({
            "dutch": entry["dutch"],
            "voice": voice,
            "word": speaker.speak(word, voice, directory) if word else None,
            "sentence": speaker.speak(entry["example"]["text"], voice, directory),
        })
    used = {clip.file for item in manifest for clip in (item["word"], item["sentence"]) if clip}
    for path in directory.glob("*.mp3"):
        if path.name not in used:
            path.unlink()
    return manifest
