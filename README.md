# 💬 ChatEasezy

**Personal Telegram Assistant with Voice Input & AI Grammar Correction**

Send Telegram messages as yourself using voice input. Your speech is transcribed, cleaned up by AI, and sent directly from your personal Telegram account.

## ✨ Features

- 🎤 **Voice Input** — Speak naturally, get clean messages
- 🤖 **AI Grammar Correction** — Groq (Llama 3.1) or Google Gemini
- 📱 **PWA** — Install on your phone like a native app
- 👤 **Send as YOU** — Messages come from your personal account, not a bot
- 📇 **Contact Management** — Save colleagues with aliases
- 🌙 **Dark Mode** — Easy on the eyes

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   PWA Frontend  │────▶│  FastAPI Backend │────▶│    Telegram     │
│   (Vercel)      │     │    (Render)      │     │   (as You)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        ▼                       ▼
   Web Speech API          Groq / Gemini
   (Transcription)        (Grammar Fix)
```

## 🚀 Quick Start

### Prerequisites

1. **Telegram API credentials** from [my.telegram.org](https://my.telegram.org)
2. **Groq API key** from [console.groq.com](https://console.groq.com/keys) (free)
3. **Gemini API key** (optional backup) from [aistudio.google.com](https://aistudio.google.com/app/apikey)

### Step 1: Get Telegram Session String

Run this locally to authenticate with Telegram:

```bash
cd backend
pip install telethon
python -c "
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input('API ID: '))
api_hash = input('API Hash: ')
phone = input('Phone (+91...): ')

with TelegramClient(StringSession(), api_id, api_hash) as client:
    client.start(phone=phone)
    print('\\nYour session string (save this!):\\n')
    print(client.session.save())
"
```

Save the session string — you'll need it for deployment.

### Step 2: Deploy Backend to Render

1. Fork/push this repo to GitHub
2. Go to [render.com](https://render.com) → **New** → **Web Service**
3. Connect your GitHub repo
4. Select the `backend` directory as root
5. Set environment variables:
   - `TELEGRAM_API_ID` — Your API ID
   - `TELEGRAM_API_HASH` — Your API Hash
   - `TELEGRAM_PHONE` — Your phone number
   - `TELEGRAM_SESSION_STRING` — From Step 1
   - `GROQ_API_KEY` — Your Groq key
   - `GEMINI_API_KEY` — (Optional) Your Gemini key
   - `AI_PROVIDER` — `groq` or `gemini`
6. Deploy! Note your backend URL (e.g., `https://chateaszy-backend.onrender.com`)

### Step 3: Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New** → **Project**
2. Import your GitHub repo
3. Set **Root Directory** to `frontend`
4. Add environment variable:
   - `VITE_API_URL` — Your Render backend URL
5. Deploy!

### Step 4: Install PWA

1. Open your Vercel URL on your phone
2. **iOS**: Tap Share → "Add to Home Screen"
3. **Android**: Tap menu → "Install app" or "Add to Home Screen"

## 🛠️ Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your credentials

uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Create .env file
cp .env.example .env
# Set VITE_API_URL=http://localhost:8000

npm run dev
```

## 📁 Project Structure

```
chateaszy/
├── backend/
│   ├── main.py              # FastAPI server
│   ├── telegram_client.py   # Telethon integration
│   ├── grammar_fixer.py     # AI grammar correction
│   ├── requirements.txt
│   ├── render.yaml          # Render deployment config
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main React app
│   │   ├── index.css        # Styles
│   │   └── main.jsx
│   ├── index.html
│   ├── vite.config.js       # PWA config
│   └── .env.example
│
├── docker-compose.yml       # Local dev with Docker
└── README.md
```

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/contacts` | List all contacts |
| POST | `/api/contacts` | Add a contact |
| DELETE | `/api/contacts/{id}` | Delete a contact |
| POST | `/api/grammar/fix` | Fix grammar in text |
| POST | `/api/message/send` | Send Telegram message |
| GET | `/api/telegram/status` | Check Telegram connection |

## 🔐 Security Notes

- Never commit `.env` files or session strings
- The Telegram session string gives full access to your account — keep it secret!
- Use environment variables for all credentials
- The PWA only works over HTTPS (required for microphone access)

## 📝 License

MIT — Use freely, modify as needed!

---

Built with ❤️ by Kapil Thakare
