# Cortx

Cortx is an AI-powered desktop web research assistant that performs intent analysis, web discovery, scraping, and source-cited answer synthesis.

## Current Status

This repository now includes a working multi-tier research pipeline.

- Phase 1 (Foundation): complete
- Phase 2 (Scraper Engine): complete
- Phase 3 (Search + Cache): complete
- Phase 4 (AI Pipeline): complete (local-only Ollama mode)

Detailed tracker: `Docs/PHASE_STATUS.md`

## Quick Start

1. Create the required virtual environment named `cortx-venv`:
   - `python -m venv cortx-venv`
2. Activate it:
   - Windows PowerShell: `./cortx-venv/Scripts/Activate.ps1`
3. Install dependencies into `cortx-venv`:
   - `python -m pip install -r requirements.txt`
4. Install Playwright browser:
   - `playwright install chromium`
5. Copy `.env.example` to `.env` and set values as needed.
6. Run a query:
   - `python main.py --query "What is retrieval augmented generation?"`
7. Run the desktop UI:
   - `python main.py --gui`

## Windows One-Command Launcher

Use `run_cortx.bat` from the repository root to bootstrap and run the app.

What it does:
- Ensures `cortx-venv` exists
- Installs dependencies from `requirements.txt`
- Ensures Playwright Chromium is installed
- Checks for and pulls `llama3.1:8b-instruct-q5_K_M` via Ollama if missing

Usage examples:
- Interactive mode: `run_cortx.bat`
- Single query: `run_cortx.bat --query "What is retrieval augmented generation?"`
- GUI mode: `run_cortx.bat --gui`

## Notes

- The current implementation intentionally prioritizes reliability and graceful fallback over advanced model integration.
- Network calls are best-effort. If search/scrape fails, the app returns an explanatory fallback response.
- LLM execution is local-only via Ollama (`llama3.1:8b-instruct-q5_K_M`).
- Desktop UI includes built-in light and dark theme support with an iOS-style switch.
