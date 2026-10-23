"""Local microphone, VAD, and speech-to-text pipeline (Milestone 2).

Heavy speech dependencies are imported lazily so non-speech H.A.N.N.I. commands
remain usable even before the optional ``speech`` extra is installed.
"""

from hanni.speech.attention import AttentiveTextBridge, RoutedSpeech, SpeechAttentionRouter
from hanni.speech.barge_in import BargeInClassifier, BargeInDecision
from hanni.speech.buffer import AudioBuffer, EphemeralBuffer, TranscriptBuffer
from hanni.speech.microphone import MicrophoneCapture, MicrophoneDevice, MicrophoneError, SpeechDependencyError, list_input_devices
from hanni.speech.pipeline import SpeechToTextPipeline, create_pipeline
from hanni.speech.live import PUMP_FINISHED, PumpFailure, TranscriptPump
from hanni.speech.relevance import RelevanceDecision, SpeechRelevanceClassifier
from hanni.speech.stt import FasterWhisperTranscriber, SttError
from hanni.speech.types import AudioChunk, TranscriptRecord, Transcription
from hanni.speech.tts import TtsEngine, TtsError, TtsPlayback, TtsVoice, WindowsSapiTts, create_tts, list_windows_voices, split_for_speech
from hanni.speech.vad import SileroVad, Utterance, UtteranceSegmenter, VadDecision

__all__ = [
    "AttentiveTextBridge",
    "BargeInClassifier",
    "BargeInDecision",
    "AudioBuffer",
    "AudioChunk",
    "EphemeralBuffer",
    "FasterWhisperTranscriber",
    "MicrophoneCapture",
    "MicrophoneDevice",
    "MicrophoneError",
    "RelevanceDecision",
    "RoutedSpeech",
    "SileroVad",
    "SpeechAttentionRouter",
    "SpeechDependencyError",
    "SpeechRelevanceClassifier",
    "SpeechToTextPipeline",
    "TranscriptPump",
    "PumpFailure",
    "PUMP_FINISHED",
    "SttError",
    "TranscriptBuffer",
    "TranscriptRecord",
    "Transcription",
    "Utterance",
    "UtteranceSegmenter",
    "VadDecision",
    "TtsEngine",
    "TtsPlayback",
    "TtsError",
    "TtsVoice",
    "WindowsSapiTts",
    "create_pipeline",
    "create_tts",
    "list_input_devices",
    "list_windows_voices",
    "split_for_speech",
]
