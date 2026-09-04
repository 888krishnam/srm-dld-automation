"""
Single SLO Safe Test Script (Dry-Run / Local Verification)
-----------------------------------------------------------
1. Downloads 1011.pdf and 1011.docx
2. Extracts text from both files
3. Deduplicates and generates solutions with AI
4. Compiles the Answer PDF locally in generated_answers/
5. (DOES NOT SUBMIT TO PORTAL - Safe for inspection)
"""
import os
import config
from api_client import SRMClient
import solver
import pdf_generator

def run_test(session_id=101, slo_num=1):
    slo_code = f"{session_id}{slo_num}"
    pdf_name = f"{slo_code}.pdf"
    docx_name = f"{slo_code}.docx"

    print(f"\n=======================================================")
    print(f"  🧪 TESTING SINGLE SLO: {slo_code} (Unit 1, Session 1, SLO {slo_num})")
    print(f"=======================================================\n")

    client = SRMClient()

    # Step 1: Download both PDF and DOCX
    print(f"[*] Step 1: Downloading worksheets ({pdf_name} and {docx_name})...")
    local_pdf = client.download_worksheet(pdf_name, file_type="pdf")
    local_docx = client.download_worksheet(docx_name, file_type="docx")

    print(f"    -> PDF Path:  {local_pdf}")
    print(f"    -> DOCX Path: {local_docx}")

    if not local_pdf and not local_docx:
        print("\n[-] Error: Could not download either PDF or DOCX. Check your auth token or network.")
        return

    # Step 2: Solve with AI (extracting from both PDF and distinct DOCX questions)
    print(f"\n[*] Step 2: Generating technical solutions with Gemini AI...")
    primary_qa, additional_docx_qa = solver.solve_worksheet_pair(
        local_pdf=local_pdf,
        local_docx=local_docx,
        session_id=session_id,
        slo_num=slo_num
    )

    if not primary_qa:
        print("[-] Could not generate solutions. Make sure GEMINI_API_KEY is valid.")
        return

    print(f"\n[+] Successfully resolved {len(primary_qa)} primary question(s):")
    for idx, item in enumerate(primary_qa, 1):
        print(f"    Q{idx}: {item.get('question', '')[:90]}")
        ans_preview = item.get('answer', '')[:100].replace('\n', ' ')
        print(f"       -> {ans_preview}...")

    if additional_docx_qa:
        print(f"\n[+] Found {len(additional_docx_qa)} additional question(s) in DOCX:")
        for idx, item in enumerate(additional_docx_qa, len(primary_qa) + 1):
            print(f"    Q{idx} [DOCX]: {item.get('question', '')[:90]}")
            ans_preview = item.get('answer', '')[:100].replace('\n', ' ')
            print(f"       -> {ans_preview}...")

    # Step 3: Generate Local Test PDF
    print(f"\n[*] Step 3: Compiling Answer PDF...")
    output_pdf_name = f"TEST_Answer_{config.COURSE_CODE}_{slo_code}.pdf"
    output_path = pdf_generator.generate_assignment_pdf(
        session_id=session_id,
        slo_num=slo_num,
        qa_list=primary_qa,
        output_filename=output_pdf_name,
        additional_qa_list=additional_docx_qa,
        additional_title="Additional Questions from DOCX Worksheet"
    )

    print(f"\n🎉 DONE! Generated test answer sheet:")
    print(f"   📂 File: {output_path}")
    print(f"   (You can open and review this PDF locally before submitting anything!)")

if __name__ == "__main__":
    run_test()
