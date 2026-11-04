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

### env-example-placeholder

`.env.example` is tracked by git and must keep its secret values blank — it is a template, not a config. Real values go in `.env`, which is gitignored. There is deliberately no default passcode, so a filled-in `.env.example` is a leak to restore before any commit.

Line endings in this repo are LF in the committed files, and `core.autocrlf` is unset. A file saved by a Windows editor therefore shows as modified with no content change, its size differing by roughly the line count; that diff is line-ending noise and can be discarded with `git checkout --`, not investigated as an edit.

<!-- ditambahkan 2026-10-24T11:20:58.848Z -->
