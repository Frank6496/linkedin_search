
"""
LinkedIn Search App (USA-focused) — FastAPI + CLI
Author: ChatGPT

UI alignment tweaks (2025-10-15):
- Consistent heights for inputs/selects.
- Grid refined to align fields in tidy rows.
- Mobile-friendly spacing.

Hosting helpers added in repo:
- Dockerfile
- Procfile (for Render/Railway/Heroku-like PaaS)
"""
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import httpx, os, re, argparse, json
from typing import Optional, Dict, Any

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY", "80758a360a8adaf14cb44c24f9510ac49a7615835fd6a569e128ce441408bbea")
SERPAPI_ENDPOINT = "https://serpapi.com/search"
ENGINE = "google"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

US_STATE_ABBR = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS",
    "MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
}

US_HINTS = [
    "United States", "USA", "U.S.", "US-based", "US", "U.S.A", "American"
]

EDU_MAP = {
    "phd": [r"ph\.?d\.?", r"doctor of philosophy", r"doctoral", r"phd"],
    "ms":  [r"m\.?s\.?", r"msc", r"master'?s", r"m\.?sc\.?"],
    "bs":  [r"b\.?s\.?", r"bsc", r"b\.?sc\.?", r"bachelor'?s"]
}

SUBJECT_SYNONYMS = {
    "math": ["mathematics", "applied mathematics", "statistics", "math"],
    "physics": ["physics", "applied physics", "astrophysics", "condensed matter"],
    "chem": ["chemistry", "chemical", "analytical chemistry", "organic chemistry", "inorganic chemistry", "physical chemistry"],
    "bio": ["biology", "biological", "biochemistry", "molecular biology", "neuroscience"],
    "cs": ["computer science", "computing", "software engineering", "machine learning", "ai", "artificial intelligence"],
    "ee": ["electrical engineering", "electronics", "signal processing"],
    "me": ["mechanical engineering", "mechanical"],
    "ce": ["civil engineering", "civil"],
    "mat_sci": ["materials science", "materials engineering", "materials"],
}

import re
NAME_SEP_RE = re.compile(r"[^a-z]+")
def norm(s: str) -> str:
    return NAME_SEP_RE.sub(" ", s.lower()).strip()

def initials_variants(first: Optional[str], last: Optional[str]):
    v = []
    if first and last:
        f = first.strip(); l = last.strip()
        v += [f"{f} {l}", f"{f[0]}. {l}", f"{f} {l[0]}.", f"{f[0]} {l}", f"{f} {l[0]}", f"{l}, {f}"]
    elif first:
        v += [first.strip(), first.strip()[0]]
    elif last:
        v += [last.strip()]
    # unique
    seen = set(); out = []
    for item in v:
        if item not in seen: out.append(item); seen.add(item)
    return out

def build_query(first: Optional[str], last: Optional[str], subject: Optional[str], education: Optional[str]) -> str:
    name_bits = initials_variants(first, last)
    name_clause = " OR ".join([f"\"{n}\"" for n in name_bits if n])
    subj_terms = []
    if subject:
        s = subject.lower().strip()
        subj_terms = SUBJECT_SYNONYMS.get(s, [s])
    subj_clause = " OR ".join([f"\"{t}\"" for t in subj_terms]) if subj_terms else ""

    edu_clause = ""
    if education:
        key = education.lower().strip()
        if key in EDU_MAP:
            edu_clause = " OR ".join([f"\"{pat.strip('^$')}\"" for pat in EDU_MAP[key]])

    location_clause = "\"United States\" OR USA OR (site:us.linkedin.com/in)"
    parts = [ "site:linkedin.com/in", f"({name_clause})" ]
    if subj_clause: parts.append(f"({subj_clause})")
    if edu_clause:  parts.append(f"({edu_clause})")
    parts.append(f"({location_clause})")
    return " ".join(parts)

def is_us_snippet(text: str) -> bool:
    t = text or ""
    if any(h.lower() in t.lower() for h in US_HINTS): return True
    for ab in US_STATE_ABBR:
        if re.search(rf"[,\s]({ab})(\s|$)", t): return True
    return False

def matches_education(text: str, education: Optional[str]) -> bool:
    if not education: return True
    pats = EDU_MAP.get(education.lower().strip(), [])
    return any(re.search(pat, text, flags=re.I) for pat in pats)

def matches_subject(text: str, subject: Optional[str]) -> bool:
    if not subject: return True
    syns = SUBJECT_SYNONYMS.get(subject.lower().strip(), [subject])
    return any(re.search(rf"\b{re.escape(s)}\b", text, flags=re.I) for s in syns)

def matches_name(title: str, first: Optional[str], last: Optional[str]) -> bool:
    title_n = norm(title)
    if first and last:
        return (norm(first) in title_n and norm(last) in title_n) or \
               (norm(f"{first} {last}") in title_n) or \
               (norm(f"{last}, {first}") in title_n)
    if first: return norm(first) in title_n
    if last:  return norm(last) in title_n
    return True

async def serpapi_search(query: str, num: int = 10) -> Dict[str, Any]:
    if not SERPAPI_KEY:
        return {"error": "SERPAPI_API_KEY environment variable is not set."}
    params = {
        "api_key": SERPAPI_KEY, "engine": ENGINE, "q": query,
        "num": num, "hl": "en", "gl": "us", "safe": "active",
    }
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        r = await client.get(SERPAPI_ENDPOINT, params=params); r.raise_for_status()
        return r.json()

def extract_results(payload: Dict[str, Any]):
    return [
        {"title": it.get("title",""), "link": it.get("link",""), "snippet": it.get("snippet","")}
        for it in payload.get("organic_results", [])
    ]

def filter_results(items, first, last, subject, education):
    filtered, seen = [], set()
    for it in items:
        t = it.get("title",""); s = it.get("snippet",""); blob = f"{t} {s}".strip()
        if not matches_name(t, first, last): continue
        if not matches_subject(blob, subject): continue
        if not matches_education(blob, education): continue
        if not is_us_snippet(blob) and "us.linkedin.com/in" not in it.get("link",""): continue
        if it["link"] in seen: continue
        seen.add(it["link"]); filtered.append(it)
    return filtered

app = FastAPI(title="LinkedIn Search (USA)")

@app.get("/", response_class=HTMLResponse)
async def home(req: Request):
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LinkedIn Search — USA</title>
  <style>
    :root { --radius: 12px; --pad: 12px; }
    * { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; padding: 24px; max-width: 900px; margin: auto; }
    h1 { margin: 0 0 8px; }
    p { margin: 8px 0 16px; color: #333; }
    .card { border: 1px solid #e5e5e5; border-radius: var(--radius); padding: 16px; margin: 12px 0; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }
    label { display:block; font-weight: 600; margin-bottom: 6px; }
    input, select {
      width:100%; padding:10px 12px; border-radius: var(--radius);
      border:1px solid #cfcfcf; outline: none;
      height: 44px; line-height: 22px;
      background: #fff;
    }
    input:focus, select:focus { border-color: #111; box-shadow: 0 0 0 3px rgba(0,0,0,0.06); }
    button { padding:12px 16px; border:none; border-radius: var(--radius); background:#111; color:white; cursor:pointer; margin-top: 8px; }
    .muted { color:#666; font-size: 14px; }
    .badge { display:inline-block; padding:2px 8px; border-radius:999px; background:#eee; font-size:12px; margin-left:8px;}
    form { display:block; }
  </style>
</head>
<body>
  <h1>LinkedIn Search — USA</h1>
  <p>Find public LinkedIn profiles by name + domain filters (education & subject). Data source: SerpAPI (Google).</p>
  <form id="f">
    <div class="grid">
      <div><label>First name</label><input name="first" placeholder="Jane" /></div>
      <div><label>Last name</label><input name="last" placeholder="Doe" /></div>
      <div>
        <label>Education</label>
        <select name="education">
          <option value="">Any</option>
          <option value="phd">PhD</option>
          <option value="ms">MS</option>
          <option value="bs">BS</option>
        </select>
      </div>
      <div><label>Subject/Domain</label><input name="subject" placeholder="biology" /></div>
      <div><label>Max results</label><input name="max_results" type="number" value="20" min="1" max="100" /></div>
    </div>
    <p class="muted">Requires <code>SERPAPI_API_KEY</code> in environment.</p>
    <button type="submit">Search</button>
  </form>
  <div id="out"></div>
<script>
const f = document.getElementById('f');
const out = document.getElementById('out');
f.addEventListener('submit', async (e) => {
  e.preventDefault();
  out.innerHTML = '<p>Searching…</p>';
  const form = new FormData(f);
  const params = new URLSearchParams(form);
  const res = await fetch('/search?' + params.toString());
  const data = await res.json();
  if (data.error) {
    out.innerHTML = '<div class="card"><b>Error:</b> ' + data.error + '</div>';
    return;
  }
  if (!data.results || data.results.length === 0) {
    out.innerHTML = '<div class="card">No results found.</div>';
    return;
  }
  out.innerHTML = data.results.map(r => `
    <div class="card">
      <div><a href="${r.link}" target="_blank">${r.title}</a></div>
      <div class="muted">${r.snippet || ''}</div>
      <div class="muted">Source: <span class="badge">Google via SerpAPI</span> | US-filtered</div>
    </div>
  `).join('');
});
</script>
</body>
</html>
    """.strip()

class SearchParams(BaseModel):
    first: Optional[str] = None
    last: Optional[str] = None
    subject: Optional[str] = None
    education: Optional[str] = None
    max_results: int = 20

from fastapi.responses import JSONResponse
from fastapi import Query

@app.get("/search")
async def search(
    first: Optional[str] = Query(None),
    last: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    education: Optional[str] = Query(None, pattern="^(phd|ms|bs)?$"),
    max_results: int = Query(20, ge=1, le=100)
):
    if not (first or last):
        return JSONResponse({"error": "Provide at least first or last name."}, status_code=400)
    q = build_query(first, last, subject, education)
    payload = await serpapi_search(q, num=max_results)
    if "error" in payload:
        return JSONResponse(payload, status_code=400)
    items = extract_results(payload)
    filtered = filter_results(items, first, last, subject, education)
    return {"query": q, "results": filtered}
