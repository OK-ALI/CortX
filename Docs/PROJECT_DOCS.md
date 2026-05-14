# CortX Project Documentation

## Overview

CortX is an AI-powered desktop web research assistant designed to perform intent analysis, web discovery, scraping, and source-cited answer synthesis. It combines a robust backend pipeline with a polished PyQt6-based user interface to provide an intuitive and reliable research tool.

The application supports multiple modes: command-line queries, interactive prompts, and a full desktop GUI with advanced features like dark/light themes, smooth animations, contextual interactions, and persistent conversation memory.

## Features

### Core Functionality
- **Intent Analysis**: Analyzes user queries to understand research intent and generate targeted search queries.
- **Web Discovery**: Uses DuckDuckGo search to discover relevant URLs.
- **Intelligent Scraping**: Multi-tier scraping engine with fallback mechanisms (httpx, Playwright, Selenium) to handle anti-bot measures.
- **Answer Synthesis**: Leverages LangChain and local LLMs (Ollama) to synthesize coherent, source-cited answers.
- **Caching and Persistence**: LanceDB-based storage for conversations, messages, and scraped content to improve performance and enable follow-up queries.

### User Interface
- **PyQt6 Desktop App**: Modern, responsive GUI with chat-like interface.
- **Themes**: Dark and light themes with smooth transitions.
- **Animations**: Custom motion framework with profiles (cinematic default) for entrance/exit effects, pulses, and scroll-following reveals.
- **Contextual Interactions**: Right-click menus, selected-text actions (ask/explain/update), context strips, and clickable context jumps.
- **Sidebar**: Resizable chat history with animations and export options.
- **Input Composer**: Autosizing text editor with context hints and slide animations.

### Advanced Features
- **Dynamic Follow-up Intent**: Standalone-by-default behavior; context only used when explicitly selected.
- **Export Options**: Export conversations in various formats.
- **Confirmation Dialogs**: For destructive actions like deleting chats.
- **Icon Support**: PNG icons with aspect-ratio preservation for theme toggles.

## Architecture

### Backend
- **AI Pipeline** (`backend/ai/`): Orchestrates the research process using LangChain LCEL chains.
  - `pipeline.py`: Main pipeline class handling intent, search, scraping, and synthesis.
  - `followup_intent.py`: Resolves follow-up queries with explicit context gating.
  - `intent_chain.py`, `query_chain.py`, `synth_chain.py`: Specialized chains for intent extraction, query generation, and answer synthesis.
  - `llm_manager.py`: Manages LLM clients (Ollama primary, Groq fallback).
- **Scraper** (`backend/scraper/`): Multi-tier scraping with robots.txt compliance and rate limiting.
  - `scraper_engine.py`: Main engine coordinating scrapers.
  - `httpx_scraper.py`, `playwright_scraper.py`, `selenium_scraper.py`: Individual scraper implementations.
- **Search** (`backend/search/`): Web discovery using DDGS.
- **Processor** (`backend/processor/`): Text cleaning, ranking, and truncation utilities.
- **Utils** (`backend/utils/`): Configuration, logging, startup checks, rate limiting.

### Frontend
- **Main Window** (`frontend/main_window.py`): Top-level UI orchestration.
- **Chat Widget** (`frontend/chat_widget.py`): Chat timeline with animations.
- **Input Bar** (`frontend/input_bar.py`): Composer with context strip.
- **Sidebar** (`frontend/sidebar.py`): Chat history management.
- **UI Motion** (`frontend/ui_motion.py`): Animation utilities with profile-aware timing.
- **Styles** (`frontend/styles/`): QSS themes for dark/light modes.
- **Theme Switch** (`frontend/theme_switch.py`): Toggle with icon support.

### Database
- **LanceDB** (`database/`): Vector database for caching and conversation storage.
  - `lance_store.py`: Main store interface.
  - `vector_index.py`: Embedding-based indexing.

### Configuration
- **Settings** (`config/settings.yaml`): App configuration.
- **Prompts** (`config/prompts.yaml`): LLM prompt templates.

## Setup

### Prerequisites
- Python 3.8+
- Ollama (for local LLM)
- Playwright browsers

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/CortX.git
   cd CortX
   ```

2. Create virtual environment:
   ```bash
   python -m venv cortx-venv
   ```

3. Activate it:
   - Windows: `cortx-venv\Scripts\Activate.ps1`
   - Linux/Mac: `source cortx-venv/bin/activate`

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Install Playwright browser:
   ```bash
   playwright install chromium
   ```

6. Configure environment:
   - Copy `.env.example` to `.env`
   - Set required values (e.g., API keys if using Groq fallback)

7. Pull Ollama model:
   ```bash
   ollama pull llama3.1:8b-instruct-q5_K_M
   ```

### Windows One-Command Launcher
Use `run_cortx.bat` to bootstrap and run:
- Interactive: `run_cortx.bat`
- Query: `run_cortx.bat --query "your query"`
- GUI: `run_cortx.bat --gui`

## Usage

### Command Line
- Single query: `python main.py --query "What is RAG?"`
- Interactive: `python main.py --interactive`
- GUI: `python main.py --gui`

### Desktop App
Launch with `--gui`. Features include:
- Type queries in the composer.
- Right-click messages for actions.
- Select text for quick ask/explain/update.
- Use context strip for follow-up with specific context.
- Toggle themes, export chats, etc.

## Development

### Testing
Run tests with pytest:
```bash
pytest
```

### Code Structure
- Follow modular design with clear separation of concerns.
- Use type hints and dataclasses.
- Async/await for I/O operations.

### Contributing
1. Fork the repository.
2. Create a feature branch.
3. Make changes with tests.
4. Submit a pull request.

## License

MIT License. See LICENSE file for details.

## Changelog

- **v1.0**: Initial release with full pipeline and UI.</content>
<parameter name="filePath">D:\Projects\CortX\Docs\PROJECT_DOCS.md