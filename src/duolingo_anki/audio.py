import hashlib
import re
from dataclasses import dataclass
from functools import cached_property
from importlib.metadata import version
from pathlib import Path

import numpy as np
import soundfile as sf

MODEL = "supertonic-3"
LANGUAGE = "nl"
VOICES = ("F1", "M1")
NOTE = re.compile(r"\([^)]*\)")
ALTERNATIVES = re.compile(r"\s*/\s*")
PATTERN_MARKERS = ("...", "…", "+")


def digest(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def voice_for(dutch: str) -> str:
    return VOICES[digest(dutch)[0] % len(VOICES)]


def spoken_word(dutch: str) -> str | None:
    if any(marker in dutch for marker in PATTERN_MARKERS) or dutch.startswith("-") or re.search(r"\w-(\(|$)", dutch):
        return None
    text = NOTE.sub("", dutch).replace("|", "")
    return ", ".join(part for part in ALTERNATIVES.split(" ".join(text.split())) if part) or None


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
    def styles(self) -> dict:
        return {voice: self.engine.get_voice_style(voice_name=voice) for voice in VOICES}

    def speak(self, text: str, voice: str, directory: Path) -> Clip:
        clip = Clip(text, file_name(text, voice))
        path = directory / clip.file
        if not path.exists():
            np.random.seed(int.from_bytes(digest(text)[:4]))
            samples, _ = self.engine.synthesize(text, voice_style=self.styles[voice], lang=LANGUAGE)
            sf.write(path, np.asarray(samples).reshape(-1), self.engine.sample_rate, format="MP3")
        return clip


def build_audio(entries: list[dict], directory: Path, speaker: Speaker) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    for entry in entries:
        voice = voice_for(entry["dutch"])
        word = spoken_word(entry["dutch"])
        manifest.append({
            "dutch": entry["dutch"],
            "voice": voice,
            "word": speaker.speak(word, voice, directory) if word else None,
            "sentence": speaker.speak(entry["example"]["text"], voice, directory),
        })
    return manifest
