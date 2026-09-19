# Resume demo deployment

This public demo intentionally runs with payment disabled and gives each newly
registered account two parsing credits. It also caps the whole site at 20 import
tasks per day. API credentials must be entered as secret environment variables
in Render and must never be committed to GitHub.

The free Render filesystem is ephemeral. Demo users, notes, and cache can reset
after a restart or idle shutdown. The cloud demo uses TikHub-provided text and an
external text model; local Whisper/OCR remain available only in the full local or
paid-server build.

Deploy through `render.yaml`, set `TIKHUB_API_KEY` and `OPENAI_API_KEY`, and use
the generated `onrender.com` URL in the resume.

