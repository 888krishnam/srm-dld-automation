"""
Setup Profile Utility:
Automatically configures .env from an SRMIST portal AUTH_TOKEN or copied cURL command.
Decodes the JWT token and auto-fills student details, course codes, and batch IDs.
"""
import os
import sys
import re
import json
import base64
import time

def extract_token_from_input(text: str) -> str:
    """Extracts Bearer token from either a raw token or a full curl command."""
    text = text.strip()
    # Case 1: Copied from curl header (e.g. -H 'Authorization: Bearer :eyJ...' or Authorization: Bearer eyJ...)
    auth_match = re.search(r"Authorization:\s*(Bearer\s*:?[A-Za-z0-9_\-\.]+)", text, re.IGNORECASE)
    if auth_match:
        return auth_match.group(1).strip()

    # Case 2: Just raw JWT starting with eyJ
    raw_jwt_match = re.search(r"(eyJ[A-Za-z0-9_\-\.]+\.eyJ[A-Za-z0-9_\-\.]+\.[A-Za-z0-9_\-\.]+)", text)
    if raw_jwt_match:
        return f"Bearer :{raw_jwt_match.group(1).strip()}"

    # Case 3: Already starts with Bearer
    if text.lower().startswith("bearer"):
        return text

    return text

def decode_jwt(token_str: str) -> dict:
    """Decodes JWT payload without external libraries."""
    raw = token_str.replace("Bearer :", "").replace("Bearer ", "").strip()
    parts = raw.split(".")
    if len(parts) < 2:
        return {}
    payload_b64 = parts[1]
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return {}

def flush_input_buffer():
    """Flushes any residual unread characters in the terminal's stdin buffer."""
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass


def read_user_input_token() -> str:
    """
    Reads pasted input from terminal, supporting multi-line pastes such as complete cURL commands.
    """
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:])

    print("💡 NOTE: Open the specific course you want solved on the portal")
    print("   BEFORE copying the token! (To switch courses later, re-run this script).\n")
    print("📋 Paste your AUTH_TOKEN or full cURL from Chrome DevTools below:")
    print("   (Paste it, then press Enter if needed):\n")

    try:
        first_line = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""

    lines = [first_line]
    is_curl = first_line.startswith("curl") or first_line.endswith("\\")

    # Drain any remaining lines from the paste buffer (e.g. multi-line cURL commands)
    try:
        import select
        wait_time = 0.2 if is_curl else 0.05
        while True:
            rlist, _, _ = select.select([sys.stdin], [], [], wait_time)
            if rlist:
                line = sys.stdin.readline()
                if not line:
                    break
                lines.append(line.rstrip("\r\n"))
            else:
                if lines and lines[-1].strip().endswith("\\"):
                    wait_time = 0.3
                    continue
                break
    except Exception:
        # Fallback if select is not available (e.g. Windows)
        while lines[-1].strip().endswith("\\"):
            try:
                lines.append(input().strip())
            except (EOFError, KeyboardInterrupt):
                break

    # Flush any trailing bytes so subsequent input prompts are clean
    flush_input_buffer()
    return "\n".join(lines)


def main():
    print("\n=======================================================")
    print("  🛠️  SRMIST DLD AUTOMATION — ONE-CLICK AUTO-SETUP")
    print("=======================================================\n")

    # Step 1: Obtain Token
    token_input = read_user_input_token()

    if not token_input:
        print("\n[-] No input provided. Exiting.")
        sys.exit(1)

    auth_token = extract_token_from_input(token_input)
    payload = decode_jwt(auth_token)

    if not payload:
        print("\n[-] Error: Could not decode token. Make sure it's a valid JWT from the portal.")
        sys.exit(1)

    # Check expiration
    exp = payload.get("exp", 0)
    if exp and time.time() > exp:
        print("\n⚠️  WARNING: The pasted token has already EXPIRED! Please copy a fresh one from Chrome.")
    else:
        remaining_hrs = (exp - time.time()) / 3600 if exp else 0
        print(f"\n✅ Token is VALID! (Expires in ~{remaining_hrs:.1f} hours)")

    # Extracted data
    reg_no = payload.get("REGISTER_NUMBER", payload.get("USER_ID", ""))
    raw_name = payload.get("FULL_NAME", "")
    dept = payload.get("DEPARTMENT", "COMPUTER SCIENCE AND ENGINEERING")
    slots = payload.get("SLOT", [])

    # Format human-readable title-case name (e.g. FIRSTNAME LASTNAME FIRSTNAME LASTNAME -> Firstname Lastname)
    # Deduplicate duplicated full names in SRM database
    name_parts = raw_name.split()
    if len(name_parts) >= 4 and name_parts[:2] == name_parts[2:4]:
        pretty_name = " ".join(p.capitalize() for p in name_parts[:2])
    elif name_parts:
        pretty_name = " ".join(p.capitalize() for p in name_parts)
    else:
        pretty_name = "Student"

    print("\n-------------------------------------------------------")
    print("  🎓 AUTO-DETECTED STUDENT DETAILS FROM TOKEN:")
    print("-------------------------------------------------------")
    print(f"  • Register No : {reg_no}")
    print(f"  • Full Name   : {pretty_name} (Portal: {raw_name})")
    print(f"  • Department  : {dept}")
    print(f"  • Enrolled Courses in Portal:")
    for idx, s in enumerate(slots, 1):
        print(f"    [{idx}] Course: {s.get('COURSE_CODE')} | Batch ID: {s.get('BATCH_ID')}")

    # Interactive or defaults
    print("\n-------------------------------------------------------")
    print("  ⚙️  CONFIGURING SETTINGS:")
    print("  💡 Tip: Press [Enter] on any prompt to keep the value in [brackets]!")
    print("-------------------------------------------------------")

    # Ensure stdin is flushed before asking interactive prompts
    flush_input_buffer()

    # Read existing .env if present for defaults
    existing_key = ""
    existing_section = ""
    existing_course = ""
    existing_course_name = ""
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    existing_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("SPECIALISATION_SECTION="):
                    existing_section = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("SECTION=") and not existing_section:
                    existing_section = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("COURSE_CODE="):
                    existing_course = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("COURSE_NAME="):
                    existing_course_name = line.split("=", 1)[1].strip().strip('"').strip("'")

    # Prompt user for PDF Name
    if sys.stdin.isatty():
        in_name = input(f"1. Name on PDF [Press Enter to keep '{pretty_name}']: ").strip()
        # Protect against accidental leftover paste lines
        if in_name.startswith(("-", "{", "curl")):
            student_name = pretty_name
        else:
            student_name = in_name if in_name else pretty_name

        sec_prompt = f" [Press Enter to keep '{existing_section}']" if existing_section else ""
        in_section = input(f"2. Specialisation & Section (e.g. CSE AIML B, CSE Core C){sec_prompt}: ").strip()
        section = in_section if in_section else existing_section

        # Auto-detect COURSE_CODE from cURL body if present
        curl_course_match = re.search(r'["\']COURSE_CODE["\']\s*:\s*["\']([^"\']+)["\']', token_input)
        detected_curl_course = curl_course_match.group(1).strip() if curl_course_match else ""

        available_courses = [s.get("COURSE_CODE") for s in slots if s.get("COURSE_CODE")]
        if detected_curl_course:
            course_default = detected_curl_course
        elif existing_course:
            course_default = existing_course
        elif available_courses:
            course_default = available_courses[0]
        else:
            course_default = "21CSE458T"
        in_course = input(f"3. Course Code [Press Enter to keep '{course_default}']: ").strip()
        course_code = in_course if in_course else course_default

        course_name_map = {
            "21CSE458T": "Wireless and Mobile Communication",
            "21CSE454T": "Distributed Computing",
            "21CSE456T": "SOFTWARE DEFINED NETWORKS",
            "21CSE452T": "Network Security",
            "21CSE301T": "Design and Analysis of Algorithms",
            "21CSE302T": "Artificial Intelligence",
            "21CSE303T": "Data Mining",
            "21CSE304T": "Machine Learning",
            "21CSE305T": "Web Technology"
        }
        default_cname = existing_course_name if existing_course_name else course_name_map.get(course_code, course_code)
        in_cname = input(f"   Course Name [Press Enter to keep '{default_cname}']: ").strip()
        course_name = in_cname if in_cname else default_cname

        key_prompt = f" [Press Enter to keep '{existing_key[:8]}...']" if existing_key else ""
        in_key = input(f"4. Gemini API Key{key_prompt}: ").strip()
        gemini_key = in_key if in_key else existing_key
    else:
        student_name = pretty_name
        section = existing_section
        course_code = existing_course if existing_course else "21CSE458T"
        course_name = existing_course_name if existing_course_name else "Wireless and Mobile Communication"
        gemini_key = existing_key

    # Match batch ID from token slots
    batch_id = ""
    for s in slots:
        if s.get("COURSE_CODE") == course_code:
            batch_id = s.get("BATCH_ID")
            break
    if not batch_id:
        batch_id = f"{course_code}_8"

    # Write .env file
    env_content = f"""# ==============================================================================
# SRMIST DLD AUTOMATION - AUTO-GENERATED CONFIGURATION
# Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}
# ==============================================================================

# --- Student Details ---
STUDENT_NAME="{student_name}"
REGISTER_NUMBER="{reg_no}"
SPECIALISATION_SECTION="{section}"
DEPARTMENT="{dept}"

# --- Course Details ---
COURSE_CODE="{course_code}"
COURSE_NAME="{course_name}"
BATCH_ID="{batch_id}"

# --- Credentials ---
GEMINI_API_KEY="{gemini_key}"
AUTH_TOKEN="{auth_token}"
"""

    with open(".env", "w", encoding="utf-8") as f:
        f.write(env_content)

    print("\n=======================================================")
    print("  🎉 .env FILE SUCCESSFULLY CREATED & AUTO-POPULATED!")
    print("=======================================================")
    print(f"  • Student Name             : {student_name}")
    print(f"  • Register No              : {reg_no}")
    print(f"  • Specialisation & Section : {section}")
    print(f"  • Course                   : {course_code} - {course_name}")
    print(f"  • Batch ID     : {batch_id}")
    print(f"  • Gemini Key   : {'Set (' + gemini_key[:8] + '...)' if gemini_key else 'None (please set in .env)'}")
    print(f"  • Auth Token   : Saved ({auth_token[:25]}...)")
    print("\n👉 Next steps:")
    print("   1. Test single SLO dry-run: python3 test_single_slo.py")
    print("   2. Run complete automation: python3 main.py --all  (on macOS: caffeinate python3 main.py --all)\n")

if __name__ == "__main__":
    main()
