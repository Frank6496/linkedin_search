
# LinkedIn Search (USA) — FastAPI + CLI

## Quickstart
```bash
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
export SERPAPI_API_KEY="your_key_here"             # Windows (Powershell): $env:SERPAPI_API_KEY="your_key_here"

# Run web
uvicorn app:app --reload --host 0.0.0.0 --port 8000
# Browse http://localhost:8000

# Run CLI
python app.py --first "Jane" --last "Doe" --subject "physics" --education phd --max-results 20
```


## Deploy / Hosting

### Option A — Docker (any VPS or Cloud Run/Fly.io/Render)
```bash
# 1) Build
docker build -t linkedin-search .
# 2) Run locally
docker run -e SERPAPI_API_KEY=YOUR_KEY -p 8000:8000 linkedin-search
# 3) Visit http://localhost:8000
```

### Option B — Render / Railway (Procfile-based)
- Create a new Web Service from this repo/zip.
- Runtime: Python 3.11
- Start command (auto from Procfile): `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Environment variable: `SERPAPI_API_KEY=YOUR_KEY`

### Option C — Bare VM (Ubuntu) with systemd + Nginx
```bash
sudo apt update && sudo apt install -y python3.11-venv nginx
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# (Optional) pip install gunicorn
# Run:
uvicorn app:app --host 0.0.0.0 --port 8000
# Nginx: reverse proxy to 127.0.0.1:8000 and add a domain + TLS (Let's Encrypt/Certbot)
```
