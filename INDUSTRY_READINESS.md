# Industry Readiness Checklist — ARXForge

Use this checklist before submitting the tool to clients. Items are marked **Done**, **In progress**, or **To do**.

---

## 1. Security

| Item | Status | Notes |
|------|--------|--------|
| No API keys or secrets in repo | **Done** | `config.yaml` and `.env` are in `.gitignore`. Use `config.example.yaml` and `.env.example` only. |
| API key from environment | **Done** | App reads `GROQ_API_KEY` from `.env` first; `config.yaml` is optional and should not contain production keys. |
| Safe file uploads | **Done** | Upload filenames sanitized to basename; optional max file size to prevent abuse. |
| No path traversal on uploads | **Done** | Saved files use `os.path.basename()` so paths like `../../etc/passwd` are rejected. |

---

## 2. Configuration & Deployment

| Item | Status | Notes |
|------|--------|--------|
| Example config without secrets | **Done** | `config.example.yaml` and `env.example` (copy to `.env`) provided. |
| Single-command run | **Done** | `streamlit run app/main.py` or `.\start_streamlit.ps1` (Windows). |
| Documented env vars | **Done** | README and this file describe `GROQ_API_KEY` and optional config. |
| Optional: Docker / production deploy | **To do** | Add `Dockerfile` and/or deployment notes if clients need container or server deploy. |

---

## 3. Reliability & Quality

| Item | Status | Notes |
|------|--------|--------|
| Phased test suite | **Done** | `python run_tests.py` runs tools, intent, planning, chaining, RAG, memory, stress. |
| Graceful handling of missing API key | **Done** | Clear error asking user to set `GROQ_API_KEY` in `.env` or `config.yaml`. |
| Graceful handling of missing/invalid ARXML | **Done** | Validation and compare flows show clear errors. |
| Logging | **Done** | Configurable logging; logs directory gitignored. |

---

## 4. User Experience & Documentation

| Item | Status | Notes |
|------|--------|--------|
| README with setup and run | **Done** | Prerequisites, install, run, example queries. |
| License clarity | **Done** | MIT; see README and LICENSE file. |
| Example queries for AI Agent | **Done** | Listed in README. |
| Compare ARXML and Validator flows | **Done** | Documented in README. |

---

## 5. Pre-Submission Quick Checks

Before handing off to a client:

1. **Remove any real secrets**  
   Ensure no `config.yaml` or `.env` with real keys is committed. Use only `config.example.yaml` and `.env.example`.

2. **Run tests**  
   ```bash
   python run_tests.py
   ```
   Fix any failing phases.

3. **Smoke test in browser**  
   - Upload an ARXML file.  
   - Run schema validation.  
   - Run Compare on two files.  
   - Run one AI Agent query (requires valid `GROQ_API_KEY`).

4. **Client setup instructions**  
   - Clone repo, create venv, `pip install -r requirements.txt`.  
   - Copy `env.example` to `.env` and set `GROQ_API_KEY`.  
   - Optionally copy `config.example.yaml` to `config.yaml` and adjust.  
   - Run with `streamlit run app/main.py`.

---

## Optional Enhancements (Post-Launch)

- **Dependency pinning**: Pin major versions in `requirements.txt` for reproducible installs.
- **Docker**: Add `Dockerfile` and `docker-compose.yml` for one-command container run.
- **New validators**: Per `docs/agent_vs_gemini_analysis.md` (undefined component refs, behavioral refs, mapping context).
- **Path robustness**: Extend `_normalize_path` for interface refs if clients use different path styles.
