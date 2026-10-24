## Catatan dari refleksi VibeCode

### tanpa-speech-to-text

The app deliberately has no speech-to-text. Voice input is limited to recording
from the microphone and uploading an audio file, with playback; the assistant
answers only questions typed into the AI Assistant.

Local Whisper is not installed on the target machine, and the project decided
against requiring it. Do not reintroduce `openai-whisper` install steps,
transcription UI, or Whisper model-size settings. If speech recognition is
wanted later, it must be an optional dependency that fails visibly rather than
a prerequisite for the Voice page to load.

<!-- ditambahkan 2026-10-22T15:05:02.925Z -->
