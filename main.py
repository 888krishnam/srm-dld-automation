"""
Main Orchestrator CLI:
Downloads worksheets, merges & deduplicates questions using AI, generates
answer PDFs locally, and submits 100% MCQ scores.

PDFs are saved to generated_answers/ organized by unit. Upload to Drive manually later.
"""
import os
import time
import random
import argparse
from tqdm import tqdm

import config
from api_client import SRMClient
import solver
import pdf_generator


def process_single_slo(client: SRMClient, session_id: int, slo_num: int, output_dir: str, force: bool = False) -> bool:
    """
    Downloads both PDF and DOCX for a specific SLO, extracts & solves questions
    (combining PDF questions with any distinct questions from DOCX), and saves the answer PDF.
    Skips if already generated unless force=True.
    """
    slo_code = f"{session_id}{slo_num}"
    output_pdf_name = f"Answer_{config.COURSE_CODE}_{slo_code}.pdf"
    output_pdf_path = os.path.join(output_dir, output_pdf_name)

    # Skip if already generated
    if not force and os.path.exists(output_pdf_path) and os.path.getsize(output_pdf_path) > 1000:
        print(f"\n[+] SLO: {slo_code} (Session {session_id}, SLO {slo_num})")
        print(f"  -> Answer PDF already exists: {output_pdf_path}. Skipping.")
        return True

    print(f"\n[+] Processing SLO: {slo_code} (Session {session_id}, SLO {slo_num})...")

    # 1. Download both PDF and DOCX worksheets
    print(f"  -> Checking for worksheets ({slo_code}.pdf and {slo_code}.docx)...")
    local_pdf = client.download_worksheet(f"{slo_code}.pdf", file_type="pdf")
    local_docx = client.download_worksheet(f"{slo_code}.docx", file_type="docx")

    if not local_pdf and not local_docx:
        print(f"  [!] Notice: Neither PDF nor DOCX found on server for SLO {slo_code}. Skipping.")
        return False

    # 2. Extract and solve using Gemini AI
    primary_qa, additional_docx_qa = solver.solve_worksheet_pair(
        local_pdf=local_pdf,
        local_docx=local_docx,
        session_id=session_id,
        slo_num=slo_num
    )

    if not primary_qa:
        print(f"  [-] Failed to generate solutions for SLO {slo_code}.")
        return False

    extra_msg = f" + {len(additional_docx_qa)} distinct from DOCX" if additional_docx_qa else ""
    print(f"  -> Total questions solved: {len(primary_qa)} primary{extra_msg}")

    # 3. Generate Answer PDF (saved locally)
    output_pdf_path = pdf_generator.generate_assignment_pdf(
        session_id=session_id,
        slo_num=slo_num,
        qa_list=primary_qa,
        output_filename=output_pdf_name,
        output_dir=output_dir,
        additional_qa_list=additional_docx_qa,
        additional_title="Additional Questions from DOCX Worksheet"
    )
    print(f"  ✅ Saved PDF: {output_pdf_path}")
    return True


def process_session(client: SRMClient, session_id: int, handle_mcqs: bool = True, force: bool = False):
    """
    Processes a complete session:
    - Downloads, solves, and saves PDFs for SLO 1 & SLO 2 (skips if already done unless force=True)
    - Submits 100% MCQ score for the session
    """
    unit_num = session_id // 100
    session_num = session_id % 100
    print(f"\n=======================================================")
    print(f"  UNIT {unit_num} | SESSION {session_num} (ID: {session_id})")
    print(f"=======================================================")

    # Organize output by unit
    unit_dir = os.path.join(config.OUTPUT_DIR, f"Unit_{unit_num}")
    os.makedirs(unit_dir, exist_ok=True)

    results = []
    for slo in [1, 2]:
        success = process_single_slo(client, session_id, slo, output_dir=unit_dir, force=force)
        results.append(success)
        time.sleep(random.uniform(1.0, 2.5))

    # Submit MCQ Assessment (100% score)
    if handle_mcqs:
        print(f"\n  [+] Submitting 100% MCQ Score for Session {session_id}...")
        mcq_res = client.submit_mcq_score(session_id, score=100)
        print(f"  -> MCQ Response: {mcq_res}")

    return any(results)


def generate_all_session_ids(unit_filter: int = None, start_session: int = None):
    """Generates session IDs, optionally filtered by unit or start session."""
    units = [unit_filter] if unit_filter else range(1, 6)
    sessions = []
    for u in units:
        for s in range(1, 10):
            sid = u * 100 + s
            if start_session and sid < start_session:
                continue
            sessions.append(sid)
    return sessions


def main():
    parser = argparse.ArgumentParser(
        description="SRMIST DLD Curricula — Download, Solve, Generate PDFs & Submit MCQs"
    )
    parser.add_argument("--test-session", type=int, default=None,
                        help="Process a single session (e.g., 101 for Unit 1 Session 1)")
    parser.add_argument("--unit", type=int, default=None,
                        help="Process all 9 sessions for a specific unit (1-5)")
    parser.add_argument("--start", "--start-session", type=int, default=None,
                        help="Start processing from a specific session ID (e.g., 302)")
    parser.add_argument("--all", action="store_true",
                        help="Process all 45 sessions (90 SLOs) across all 5 units")
    parser.add_argument("--skip-mcq", action="store_true",
                        help="Skip MCQ score submissions")
    parser.add_argument("--mcq-only", action="store_true",
                        help="Only submit MCQ scores (skip worksheet download & solving)")
    parser.add_argument("--missing", "--missing-only", action="store_true",
                        help="Scan generated_answers and only process missing SLOs")
    parser.add_argument("--force", action="store_true",
                        help="Force re-generation of PDFs even if they already exist")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Delay in seconds between sessions (default: 2.0)")

    args = parser.parse_args()

    client = SRMClient()

    # Missing-only mode: only generate PDFs that don't exist yet
    if args.missing:
        import glob
        print("\n🔍 Scanning for missing SLO answer PDFs in generated_answers/...")
        all_existing_pdfs = glob.glob(os.path.join(config.OUTPUT_DIR, "**/*.pdf"), recursive=True)
        missing_slos = []
        for u in range(1, 6):
            unit_dir = os.path.join(config.OUTPUT_DIR, f"Unit_{u}")
            os.makedirs(unit_dir, exist_ok=True)
            for s in range(1, 10):
                session_id = u * 100 + s
                for slo in [1, 2]:
                    slo_code = f"{session_id}{slo}"
                    found = any(f"_{slo_code}.pdf" in f or f"{slo_code}.pdf" in f for f in all_existing_pdfs)
                    if not found:
                        missing_slos.append((session_id, slo, unit_dir))

        if not missing_slos:
            print("🎉 Amazing! All 90 SLO PDFs are already generated. None are missing!\n")
            return

        print(f"[*] Found {len(missing_slos)} missing SLO(s):")
        for s_id, slo, _ in missing_slos:
            print(f"  • Unit {s_id//100} | Session {s_id} | SLO {slo} (Code: {s_id}{slo})")
        print(f"\n[*] Processing only the {len(missing_slos)} missing SLO(s)...\n")

        success = 0
        for s_id, slo, u_dir in tqdm(missing_slos, desc="Missing SLO Progress"):
            if process_single_slo(client, session_id=s_id, slo_num=slo, output_dir=u_dir, force=False):
                success += 1
            time.sleep(args.delay)

        print(f"\n{'='*55}")
        print(f"  ✅ Completed: {success}/{len(missing_slos)} missing PDFs generated!")
        print(f"  📂 All PDFs saved in: {os.path.abspath(config.OUTPUT_DIR)}/")
        print(f"{'='*55}\n")
        return

    if args.test_session:
        sessions_to_run = [args.test_session]
    elif args.start:
        sessions_to_run = generate_all_session_ids(unit_filter=args.unit, start_session=args.start)
    elif args.unit:
        sessions_to_run = generate_all_session_ids(unit_filter=args.unit)
    elif args.all:
        sessions_to_run = generate_all_session_ids()
    else:
        print("\n[*] No mode specified. Defaulting to Session 101 (Unit 1, Session 1).")
        print("[*] To run all 90 SLOs: python main.py --all\n")
        sessions_to_run = [101]

    # MCQ-only mode: just submit scores, no worksheet processing
    if args.mcq_only:
        print(f"[*] MCQ-Only Mode: Submitting 100% scores for {len(sessions_to_run)} session(s)...\n")
        for session_id in tqdm(sessions_to_run, desc="MCQ Submissions"):
            mcq_res = client.submit_mcq_score(session_id, score=100)
            print(f"  Session {session_id}: {mcq_res}")
            time.sleep(0.5)
        print("\n✅ All MCQ scores submitted!")
        return

    print(f"[*] Starting processing for {len(sessions_to_run)} session(s)...")
    print(f"[*] PDFs will be saved to: {os.path.abspath(config.OUTPUT_DIR)}/")
    if not args.skip_mcq:
        print(f"[*] MCQ scores will also be submitted automatically.\n")
    else:
        print(f"[*] MCQ submissions: SKIPPED (--skip-mcq)\n")

    success_count = 0
    fail_count = 0

    for session_id in tqdm(sessions_to_run, desc="Overall Progress"):
        if process_session(client=client, session_id=session_id, handle_mcqs=not args.skip_mcq, force=args.force):
            success_count += 1
        else:
            fail_count += 1
        time.sleep(args.delay)

    print(f"\n{'='*55}")
    print(f"  ✅ DONE — {success_count} sessions succeeded, {fail_count} had issues")
    print(f"  📂 All PDFs saved in: {os.path.abspath(config.OUTPUT_DIR)}/")
    print(f"{'='*55}")
    print(f"\nNext steps:")
    print(f"  1. Review the PDFs in generated_answers/")
    print(f"  2. Upload them to Google Drive manually")
    print(f"  3. Submit the Drive links on the portal")


if __name__ == "__main__":
    main()

