# ⚠️ ARCHIVED / NO LONGER FUNCTIONAL

> [!CAUTION]
> **This repository is archived and no longer maintained.**
> Due to website structure and API changes on the SRMIST DLD Curricula portal (`dld.srmist.edu.in`), this automation tool has stopped working. It is preserved here strictly for historical and reference purposes.

---

# SRMIST DLD Curricula Automation

Downloads worksheets (both **PDF** and **DOCX**), uses Gemini AI to solve questions while comparing and appending any unique questions from DOCX, generates clean, styled answer PDFs locally, and automatically submits **100% MCQ assessment scores** for all **90 SLOs (5 Units × 9 Sessions × 2 SLOs)** on the SRMIST DLD portal.

---

## 📁 Project Structure

```
dld automation/
├── config.py              # Auth token, student metadata, API endpoints
├── api_client.py          # Portal API client (PDF/DOCX downloader, MCQ submitter)
├── solver.py              # LLM engine: PDF & DOCX text extraction, comparison & solving
├── pdf_generator.py       # ReportLab: compiles styled PDFs with tables & DOCX sections
├── main.py                # Unified CLI orchestrator (batch processing, skip cache)
├── test_single_slo.py     # Safe dry-run for a single SLO (no portal submissions)
├── .env                   # Active user credentials and course details (git-ignored)
├── .env.example           # Template for other students / users
├── requirements.txt       # Dependencies (requests, pypdf, python-docx, reportlab, tqdm)
├── setup_profile.py       # One-click interactive tool to auto-configure .env from your token
├── downloads/             # Cached raw PDF and DOCX files from portal
└── generated_answers/     # Final answer PDFs organized by Unit (Unit_1 to Unit_5)
```

---

## 🚀 Quick Setup (3 Steps)

### 📦 Step 1: Install Dependencies
Open your terminal in the project directory and install the required Python packages:
```bash
pip install -r requirements.txt
```

---

### 🔑 Step 2: Get your `AUTH_TOKEN` from Chrome
1. Open the SRMIST DLD Portal in **Google Chrome** (or Edge/Brave) and log in:
   `https://dld.srmist.edu.in/ncretecurricula/`
2. **Open the specific course** you want solved.
   > ⚠️ **Important**: You must open the course page first before copying the token!
3. Press **`F12`** (or right-click anywhere on the page and select **Inspect** / **Cmd + Option + I** on Mac).
4. Switch to the **Network** tab at the top of DevTools.
5. Click on any session, or refresh the page (`Cmd + R` / `F5`).
6. In the Network tab list, click on any request (e.g. `getcircleinfo`, `mcq`, or `getfile`).
7. In the **Headers** tab on the right, scroll down to **Request Headers**.
8. Find **`Authorization:`** and copy the entire string (it looks like `Bearer :eyJhbGciOiJIUz...`).
   *(Tip: You can also just right-click any request -> **Copy** -> **Copy as cURL**!)*

> 💡 **Switching Courses Later**: If you want to solve assignments for a **different course**, simply open that course on the portal and run `python3 setup_profile.py` again!

---

### ⚡ Step 3: Run the Auto-Setup Command
Run this in your terminal and paste your token (or copied cURL):

```bash
python3 setup_profile.py
```

**What it does automatically:**
- Validates the token and tells you when it expires.
- Decodes your **Register Number**, **Full Name**, and **Department**.
- Detects your enrolled **Courses** and exact **Batch IDs**.
- Prompts for your preferred PDF display name, Specialisation & Section (e.g. CSE AIML B, CSE Core C), and Gemini API key *(press **Enter** on any prompt to keep the default value in **[brackets]**)*.
- Writes and saves your complete, ready-to-run **`.env`** file automatically!

---

## 💻 Usage

> 💡 **Tip for macOS Users**: Prefix long-running commands with `caffeinate` (e.g. `caffeinate python3 main.py --all`) to prevent your Mac from going to sleep while running in the background.

### 🧪 Safe Single SLO Test Run
```bash
python3 test_single_slo.py
```
Downloads both PDF & DOCX for SLO 1011, compares & solves them, and generates a test PDF without submitting to the portal.

### ⚡ Run All Units (with MCQ Submission)
```bash
python3 main.py --all
```
*(On macOS, you can run: `caffeinate python3 main.py --all`)*

### 🎯 Start from a Specific Session
```bash
python3 main.py --start 302
```
*(On macOS: `caffeinate python3 main.py --start 302`)*

### 📚 Process a Single Unit or Session
```bash
python3 main.py --unit 1
python3 main.py --test-session 101
```

### 🔄 Process Only Missing SLOs (No Re-generating)
If a few PDFs failed due to temporary network timeouts or API quotas, you don't need to re-run everything. Run:
```bash
python3 main.py --missing
```
*(Scans `generated_answers/`, finds any missing SLOs, and only generates those!)*

### 📝 MCQ-Only Submission (No PDF Generation)
```bash
python3 main.py --all --mcq-only
```

---

## 📂 Output Structure

```
generated_answers/
├── Unit_1/
│   ├── Answer_21CSE458T_1011.pdf
│   ├── Answer_21CSE458T_1012.pdf
│   └── ... (18 files)
├── Unit_2/ (18 files)
├── Unit_3/ (18 files)
├── Unit_4/ (18 files)
└── Unit_5/ (18 files)
```
Total: **90 Answer PDFs** ready to be uploaded to Google Drive!

## 🔍 How It Works

1. Downloads both `{slo_code}.docx` and `{slo_code}.pdf` from the portal
2. Extracts text and tables from both documents
3. Sends both to **Gemini** (or local Ollama) to deduplicate questions across formats
4. AI generates comprehensive academic answers for each unique question
5. `pdf_generator.py` compiles a clean PDF answer sheet with your student metadata
6. PDFs are saved locally — **nothing is submitted automatically**
