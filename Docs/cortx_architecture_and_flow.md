# CortX Architecture & Workflow Presentation Guide

If you need to explain **CortX** (e.g., in an interview, project viva, or presentation), the best approach is to break it down into **three main pillars**: The Goal, The Tech Stack, and The Pipeline Flow.

---

## 1. Project Goal (The "Elevator Pitch")
**CortX** is an autonomous, privacy-first, desktop-based AI research assistant. Similar to ChatGPT's "Search the Web" feature or Perplexity AI, it takes a user's question, searches the live internet for up-to-date facts, scrapes the relevant sites, and uses a local Large Language Model (LLM) to synthesize a highly accurate, fully-cited answer—all without relying on paid cloud APIs or compromising user privacy.

---

## 2. The Technology Stack

### Frontend (User Interface)
* **PyQt6 (Python):** The entire graphical user interface is built using PyQt6. It allows for advanced desktop integration, custom styling via QSS (Qt Style Sheets) for Light/Dark themes, and native layout management.
* **Markdown Renderer:** The responses are parsed from raw markdown into rich HTML content to render code blocks, bold text, and clickable source links cleanly in native UI components like `QTextBrowser`.

### Backend (The AI & Search Engine)
* **Ollama (Llama 3.1 8B):** Powers the "Brain" of the application locally. It handles query understanding, search formulation, and synthesizing the final conversational response.
* **LangChain (LCEL):** Used to orchestrate the prompt chains. LangChain manages how variables (like scraped text and URLs) are formatted and fed into the Ollama model.
* **DuckDuckGo Search API (`duckduckgo-search`):** Used to silently perform organic web searches based on what the user asks to find reference URLs.

### Scraping Engine (The "Eyes")
CortX uses a highly optimized, asynchronous multi-tier scraping mechanism:
* **Tier 1 (HTTPX & BeautifulSoup4):** The primary layer. It uses non-blocking `asyncio` to rapidly fetch HTML and parse readable text from standard websites.
* **Tier 2 (Playwright):** The fallback layer. If a site requires JavaScript to load (like modern React apps or finance sites), Playwright spawns a headless Chromium browser to perfectly simulate a human and read the dynamic data.

### Storage & Memory
* **LanceDB:** A highly efficient, embedded vector database used to store conversation history and chat logs immutably.
* **SQLite:** Used implicitly via standard Python database utilities to keep track of chat metadata on disk.

---

## 3. The Execution Flow (Step-by-Step)

When a user types a query like *"What happened with Apple stock today?"* and hits Send, here is exactly what happens behind the scenes:

> [!NOTE]
> All these steps happen sequentially within the `CortxPipeline` orchestrated in Python.

1. **Step 1: Query Analysis & Intent (LLM)**
   * The backend takes the query and feeds it to the local LLM to understand *what* the user wants. Is it a math question? A general text question? Or a time-sensitive live event? 

2. **Step 2: Search Query Generation (LLM)**
   * If the system decides it needs web data, the LLM is asked to generate optimized search engine keywords (e.g., `"Apple stock news major price movement today"`).

3. **Step 3: Web Search (DuckDuckGo)**
   * CortX takes those keywords and silently pings DuckDuckGo to grab the top 5-10 organic web URLs.

4. **Step 4: Concurrent Scraping (Asyncio + Scraper Engine)**
   * CortX launches multiple concurrent web scrapers at exactly the same time. 
   * It attempts to aggressively read all the text from those URLs using **HTTPX**. If a site throws an error or blocks bot traffic, it seamlessly falls back to **Playwright** to mimic a real web browser.

5. **Step 5: Content Ranking & Pruning**
   * Websites contain a lot of junk (navbars, ads, footers). CortX ranks paragraphs mathematically, throwing away useless text and keeping only the paragraphs most relevant to the user's question to save memory and processing time.

6. **Step 6: LLM Synthesis**
   * CortX merges the user's original query, the highly refined web snippets, and the parsed URLs string into a massive prompt. 
   * The local Ollama model reads this contextual data and streams back a conversational, human-like response, injecting inline citations like `[1]` where it used a specific web source.

7. **Step 7: UI Rendering**
   * The text is pushed to the PyQt6 Frontend, mapped into HTML, the custom `SpinnerWidget` stops animating, and the fully cited references are appended underneath the text blob flawlessly.
