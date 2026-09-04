"""
Configuration module:
Loads user details, course settings, API credentials, and portal tokens from .env file or environment variables.
"""
import os
import json
import base64
import time


def _load_env_file(filepath=".env"):
    """Loads key-value pairs from a .env file into os.environ if not already set."""
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Strip matching surrounding quotes
                if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
                    val = val[1:-1]
                if key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        print(f"[!] Warning reading {filepath}: {e}")


# 1. Load from .env file
_load_env_file(".env")

# 2. Base API URLs
BASE_URL = os.getenv("BASE_URL", "https://dld.srmist.edu.in/ncretecurricula/server")
GET_FILE_URL = f"{BASE_URL}/curricula/admin/file/getfile"
SUBMIT_LINK_URL = f"{BASE_URL}/curricula/student/session/submitlink"
SUBMIT_MCQ_URL = f"{BASE_URL}/curricula/student/session/mcq"

# 3. Authentication Token
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "").strip()

# 4. Course Details
COURSE_CODE = os.getenv("COURSE_CODE", "21CSE458T").strip()
COURSE_NAME = os.getenv("COURSE_NAME", "Wireless and Mobile Communication").strip()
BATCH_ID = os.getenv("BATCH_ID", "").strip()

# 5. Student Details (configured via .env)
STUDENT_NAME = os.getenv("STUDENT_NAME", "Student").strip()
REGISTER_NUMBER = os.getenv("REGISTER_NUMBER", os.getenv("USER_ID", "")).strip()
USER_ID = REGISTER_NUMBER
SPECIALISATION_SECTION = os.getenv("SPECIALISATION_SECTION", os.getenv("SECTION", "")).strip()
SECTION = SPECIALISATION_SECTION  # Backwards compatibility alias
DEPARTMENT = os.getenv("DEPARTMENT", "COMPUTER SCIENCE AND ENGINEERING").strip()
FULL_NAME = os.getenv("FULL_NAME", "").strip()

# 6. Gemini AI Credentials
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# 7. Auto-extract from JWT Token if available
SLOTS = []
if AUTH_TOKEN:
    try:
        raw_jwt = AUTH_TOKEN.replace("Bearer :", "").replace("Bearer ", "").strip()
        jwt_parts = raw_jwt.split(".")
        if len(jwt_parts) >= 2:
            payload_b64 = jwt_parts[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            jwt_data = json.loads(base64.urlsafe_b64decode(payload_b64))

            # Autofill empty fields directly from JWT
            if not USER_ID:
                USER_ID = jwt_data.get("USER_ID", jwt_data.get("REGISTER_NUMBER", ""))
                REGISTER_NUMBER = USER_ID

            if not FULL_NAME:
                FULL_NAME = jwt_data.get("FULL_NAME", STUDENT_NAME)

            if not DEPARTMENT and "DEPARTMENT" in jwt_data:
                DEPARTMENT = jwt_data.get("DEPARTMENT")

            SLOTS = jwt_data.get("SLOT", [])

            # If BATCH_ID wasn't set, auto-match from SLOTS
            if not BATCH_ID and SLOTS:
                for slot in SLOTS:
                    if slot.get("COURSE_CODE") == COURSE_CODE:
                        BATCH_ID = slot.get("BATCH_ID", "")
                        break
                if not BATCH_ID and SLOTS:
                    BATCH_ID = SLOTS[0].get("BATCH_ID", "")
    except Exception:
        pass

# Final fallbacks if token/env was not provided
if not USER_ID:
    USER_ID = "STUDENT_REG_NO"
    REGISTER_NUMBER = USER_ID
if not FULL_NAME:
    FULL_NAME = STUDENT_NAME
if not BATCH_ID:
    BATCH_ID = f"{COURSE_CODE}_BATCH"
if not SLOTS:
    SLOTS = [{"COURSE_CODE": COURSE_CODE, "BATCH_ID": BATCH_ID, "SEMESTER": 7}]

# 8. Platform-Agnostic HTTP Headers
import platform
_system = platform.system()
if _system == "Windows":
    _ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
elif _system == "Linux":
    _ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
else:  # macOS / Darwin default
    _ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en",
    "Authorization": AUTH_TOKEN,
    "Connection": "keep-alive",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://dld.srmist.edu.in",
    "Referer": "https://dld.srmist.edu.in/ncretecurricula/",
    "User-Agent": _ua
}

# 9. Directories
DOWNLOAD_DIR = "downloads"
OUTPUT_DIR = "generated_answers"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def check_token_expiry() -> bool:
    """Checks if the JWT token is expired and prints a warning."""
    if not AUTH_TOKEN:
        print("\n⚠️  WARNING: AUTH_TOKEN is not set in .env!")
        print("   Please copy your token from Chrome DevTools and add it to .env.\n")
        return False
    try:
        raw_jwt = AUTH_TOKEN.replace("Bearer :", "").replace("Bearer ", "").strip()
        jwt_parts = raw_jwt.split(".")
        if len(jwt_parts) >= 2:
            payload_b64 = jwt_parts[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp = payload.get("exp", 0)
            if exp and time.time() > exp:
                print("\n⚠️  WARNING: Your JWT auth token has EXPIRED!")
                print("   Go to the portal in Chrome → DevTools (F12) → Network tab → copy a fresh 'Authorization' header.")
                print("   Then update AUTH_TOKEN in your .env file.\n")
                return False
            elif exp:
                remaining_hrs = (exp - time.time()) / 3600
                if remaining_hrs < 1:
                    print(f"\n⚠️  Token expires in {remaining_hrs*60:.0f} minutes — consider refreshing soon.\n")
    except Exception:
        pass
    return True


# Run check on import
check_token_expiry()
