# Terminal 1 — backend without hot-reload:
source .venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8088

# Terminal 2 — build the frontend and preview it:
cd frontend
npm run build
npm run preview
