"""
AI Solver module:
Extracts worksheet questions from PDF and generates high-scoring technical answers using Gemini API.
"""
import os
import json
import re
import requests
from pypdf import PdfReader
import config

GEMINI_API_KEY = getattr(config, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = getattr(config, "GEMINI_MODEL", "") or os.getenv("GEMINI_MODEL", "gemini-flash-latest")
OLLAMA_HOST = getattr(config, "OLLAMA_HOST", "") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = getattr(config, "OLLAMA_MODEL", "") or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


def extract_text_from_docx(docx_path: str) -> str:
    """Extracts all text and tables from a DOCX file."""
    if not docx_path or not os.path.exists(docx_path):
        return ""
    # Try python-docx first
    try:
        from docx import Document
        doc = Document(docx_path)
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    full_text.append(" | ".join(row_text))
        return "\n".join(full_text)
    except Exception:
        pass

    # Fallback: extract XML text from docx zip
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(docx_path) as z:
            xml_content = z.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        texts = [node.text for node in tree.iter() if node.text and node.text.strip()]
        return "\n".join(texts)
    except Exception as e:
        print(f"[-] Error reading DOCX {docx_path}: {e}")
        return ""


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts all text from a PDF file."""
    if not pdf_path or not os.path.exists(pdf_path):
        return ""
    try:
        reader = PdfReader(pdf_path)
        full_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text.append(text.strip())
        return "\n".join(full_text)
    except Exception as e:
        print(f"[-] Error reading PDF {pdf_path}: {e}")
        return ""


def _build_prompt(pdf_text: str, session_id: int, slo_num: int) -> str:
    return f"""
You are an expert professor in {config.COURSE_NAME} (Course Code: {config.COURSE_CODE}).

Below is the text extracted from the official student worksheet for Session {session_id}, SLO {slo_num}:

=== WORKSHEET CONTENT ===
{pdf_text if pdf_text else "[No Content Available]"}

YOUR INSTRUCTIONS:
1. Carefully identify all questions, exercises, fill-in-the-blanks, descriptive questions, and numerical problems present in the worksheet in sequential order.
2. For each question, provide a comprehensive, 100% accurate, high-scoring academic answer.
3. FORMATTING GUIDELINES (CRITICAL):
   - For comparisons, use bullet points or labeled sections with bold headers (e.g. **Transmitter:** ... **Receiver:** ...) rather than ASCII pipe tables (|).
   - Use bold formatting (**Term:**) for titles, headings, and important terms.
   - Use clean numbered lists (1., 2.) or hyphens (-) for lists.
   - Provide formulas, standard definitions, and step-by-step calculations where relevant.

Return ONLY a valid JSON array of objects following this exact schema:
[
  {{
    "q_num": 1,
    "question": "Exact question text here...",
    "answer": "Detailed academic answer here..."
  }}
]
"""


def _clean_json_response(raw_text: str) -> list:
    """Extracts JSON array from text even if enclosed in markdown code fences."""
    raw_text = raw_text.strip()

    # Try to extract JSON from markdown code fences using regex
    fence_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', raw_text)
    if fence_match:
        raw_text = fence_match.group(1).strip()

    # Try to find a JSON array directly
    array_match = re.search(r'(\[[\s\S]*\])', raw_text)
    if array_match:
        try:
            data = json.loads(array_match.group(1))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # Fallback: try parsing the whole text
    try:
        data = json.loads(raw_text)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "questions" in data:
            return data["questions"]
    except json.JSONDecodeError:
        print(f"  [-] Could not parse JSON from AI response. Raw text preview: {raw_text[:200]}")

    return []


def _call_llm_json(prompt: str) -> list:
    """Executes a prompt against Gemini API (with quota detection & model rotation) or Local Ollama."""
    api_keys = [k.strip() for k in GEMINI_API_KEY.split(",") if k.strip()]
    if api_keys:
        models_to_try = [
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview",
            "gemini-flash-latest",
            "gemini-3.7-flash",
            "gemini-3.5-flash",
        ]
        for key in api_keys:
            for model in models_to_try:
                for attempt in range(3):
                    try:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                        payload = {
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "responseMimeType": "application/json"
                            }
                        }
                        res = requests.post(url, json=payload, timeout=90)
                        if res.status_code == 200:
                            result_json = res.json()
                            candidates = result_json.get("candidates", [])
                            if not candidates:
                                block_reason = result_json.get("promptFeedback", {}).get("blockReason", "unknown")
                                print(f"  [-] Gemini returned no candidates (blocked: {block_reason}). Switching model...")
                                break
                            content = candidates[0].get("content", {})
                            parts = content.get("parts", [])
                            if parts and "text" in parts[0]:
                                text_out = parts[0]["text"]
                                return _clean_json_response(text_out)
                            else:
                                finish_reason = candidates[0].get("finishReason", "unknown")
                                print(f"  [-] No text content (finishReason: {finish_reason}). Trying again...")
                        elif res.status_code == 429:
                            err_text = res.text
                            if "quotaValue" in err_text or "RESOURCE_EXHAUSTED" in err_text or "Daily" in err_text:
                                print(f"  [-] {model} quota reached for today. Switching immediately to next model...")
                                break
                            else:
                                wait = (attempt + 1) * 5
                                print(f"  [-] Rate limited. Waiting {wait}s... (attempt {attempt+1}/3)")
                                import time
                                time.sleep(wait)
                        elif res.status_code == 503:
                            wait = (attempt + 1) * 4
                            print(f"  [-] {model} temporary high demand (503). Retrying in {wait}s...")
                            import time
                            time.sleep(wait)
                        else:
                            print(f"  [-] Gemini API Error ({res.status_code}): {res.text[:150]}")
                            break
                    except Exception as e:
                        print(f"  [-] Gemini request error ({model}): {e}")
                        break
                else:
                    continue
                continue

    # 2. Try Local On-Device Ollama
    try:
        print(f"  -> Using On-Device Local AI ({OLLAMA_MODEL} via Ollama)...")
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        res = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=120)
        if res.status_code == 200:
            result = res.json()
            return _clean_json_response(result.get("response", "[]"))
    except Exception as e:
        print(f"[-] Ollama connection error: {e}")

    print("\n[!] Please provide either a free GEMINI_API_KEY (aistudio.google.com) or start Ollama (`ollama run qwen2.5:7b`).")
    return []


def solve_worksheet_questions(pdf_text: str, session_id: int, slo_num: int) -> list:
    """
    Solves worksheet questions using either Gemini API (with retries & fallback) or Local Ollama.
    """
    if not pdf_text:
        return []
    prompt = _build_prompt(pdf_text, session_id, slo_num)
    return _call_llm_json(prompt)


def find_new_docx_questions(pdf_text: str, docx_text: str, session_id: int, slo_num: int) -> list:
    """
    Compares the DOCX worksheet against the PDF worksheet for a given SLO.
    Returns a list of NEW/UNIQUE questions from DOCX with solutions, or [] if all questions are identical.
    """
    if not docx_text:
        return []

    prompt = f"""
You are an expert academic professor reviewing course worksheets for {config.COURSE_NAME} (Course Code: {config.COURSE_CODE}), Session {session_id}, SLO {slo_num}.

Below are the contents of TWO versions of the official student worksheet:
Version 1 (PDF): The primary worksheet.
Version 2 (DOCX): The alternate worksheet.

=== VERSION 1: PDF WORKSHEET ===
{pdf_text}

=== VERSION 2: DOCX WORKSHEET ===
{docx_text}

TASK:
1. Carefully compare all questions, exercises, and problems in the DOCX worksheet against the questions in the PDF worksheet.
2. Determine if the DOCX worksheet contains any NEW or UNIQUE questions that were NOT already present or asked in the PDF worksheet.
   - Note: If a question is fundamentally asking for the exact same concept, formula, or answer (even with minor wording or order differences), treat it as COVERED and do NOT include it.
   - Only include questions that are genuinely NEW, EXTRA, or DIFFERENT in the DOCX version.
3. If all questions in the DOCX worksheet are already covered in the PDF, return an EMPTY JSON array: `[]`.
4. If there are genuinely new questions in the DOCX, provide comprehensive, high-scoring, academic answers for ONLY those new questions.
5. FORMATTING GUIDELINES:
   - For comparisons, use bullet points with bold headers instead of ASCII pipe tables (|).
   - Use bold formatting (**Term:**) for titles and keywords.
   - Clean numbered lists or hyphens for points.

Return ONLY a valid JSON array following this schema:
[
  {{
    "q_num": 1,
    "question": "Exact text of the NEW question from DOCX...",
    "answer": "Detailed academic answer..."
  }}
]
If no new questions exist in the DOCX, return:
[]
"""
    return _call_llm_json(prompt)


def solve_worksheet_pair(local_pdf: str, local_docx: str, session_id: int, slo_num: int) -> tuple[list, list]:
    """
    Core solver for an SLO:
    - If both PDF and DOCX exist: solves PDF questions, then compares DOCX against PDF
      and returns (primary_qa, additional_docx_qa).
    - If only PDF exists: returns (primary_qa, []).
    - If only DOCX exists: returns (primary_qa, []).
    - If neither exists: returns ([], []).
    """
    pdf_text = extract_text_from_pdf(local_pdf) if local_pdf else ""
    docx_text = extract_text_from_docx(local_docx) if local_docx else ""

    if not pdf_text and not docx_text:
        return [], []

    # Case 1: Both PDF and DOCX exist -> solve PDF, compare DOCX for distinct questions
    if pdf_text and docx_text:
        print(f"  -> Extracted text: PDF ({len(pdf_text)} chars), DOCX ({len(docx_text)} chars)")
        print(f"  -> Solving questions from PDF worksheet...")
        primary_qa = solve_worksheet_questions(pdf_text, session_id, slo_num)

        print(f"  -> Comparing DOCX against PDF for any new questions...")
        new_docx_qa = find_new_docx_questions(pdf_text, docx_text, session_id, slo_num)
        if new_docx_qa:
            print(f"  ⚡ Found {len(new_docx_qa)} additional question(s) in DOCX!")
        else:
            print(f"  ✅ All questions in DOCX are already covered in PDF.")

        return primary_qa, new_docx_qa

    # Case 2: Only PDF exists
    if pdf_text:
        print(f"  -> Extracted text: PDF ({len(pdf_text)} chars)")
        print(f"  -> Solving questions from PDF worksheet...")
        primary_qa = solve_worksheet_questions(pdf_text, session_id, slo_num)
        return primary_qa, []

    # Case 3: Only DOCX exists
    if docx_text:
        print(f"  -> Extracted text: DOCX ({len(docx_text)} chars)")
        print(f"  -> Solving questions from DOCX worksheet...")
        primary_qa = solve_worksheet_questions(docx_text, session_id, slo_num)
        return primary_qa, []

    return [], []


def deduplicate_and_solve_questions(*args, **kwargs) -> list:
    """Backwards compatibility wrapper for solve_worksheet_questions."""
    pdf_text = kwargs.get("pdf_text", "")
    session_id = kwargs.get("session_id", 101)
    slo_num = kwargs.get("slo_num", 1)

    if args:
        if len(args) >= 4:
            pdf_text = args[1] or args[0]
            session_id = args[2]
            slo_num = args[3]
        elif len(args) == 3:
            pdf_text = args[0]
            session_id = args[1]
            slo_num = args[2]

    return solve_worksheet_questions(pdf_text, session_id, slo_num)


