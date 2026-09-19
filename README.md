# Video Knowledge — AI video-to-notes demo

A UniApp + Vue 3 portfolio project that turns public Douyin/Xiaohongshu links
into structured knowledge notes. The repository contains the H5 client and a
small Python API. Payment is intentionally disabled in the resume demo.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/songxiaoxue2233/video-knowledge-resume-demo)

## Demo capabilities

- Account registration and login
- Background import tasks with progress/history
- Public-link parsing through TikHub
- Structured note generation through a compatible text-model API
- Knowledge-base CRUD, folders, tags, dashboard, search, and exports
- Free-demo safety limits: 2 imports per new account and 20 imports site-wide per day

The free cloud build prioritizes links that already expose usable text. Local
Whisper/OCR fallbacks are excluded from the lightweight resume deployment.

## Deploy on Render

1. Create a new Blueprint from this repository.
2. Set the secret environment variables `TIKHUB_API_KEY` and `OPENAI_API_KEY`.
3. Deploy using the included `render.yaml`.

Render will build the H5 client and serve it together with the Python API from
one `onrender.com` URL. Free instances can sleep after inactivity, so the first
visit may take about a minute.

## Local development

```sh
npm ci
npm run build:h5
python server/app.py
```

Copy `.env.example` to `.env.local` and add your own API credentials. Never
commit `.env.local`, databases, exports, or private keys.
