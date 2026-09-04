"""
API Client for interacting with SRMIST DLD Portal.
"""
import os
import json
import base64
import requests
import config

class SRMClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)

    def download_worksheet(self, filename: str, file_type: str = "pdf") -> str:
        """
        Downloads a worksheet (PDF or DOCX) from the portal.
        Tries direct static URL first (instant, doesn't hang if missing), then falls back to getfile API.
        Returns local filepath if successful, or None if file does not exist on server.
        """
        local_path = os.path.join(config.DOWNLOAD_DIR, filename)
        if os.path.exists(local_path) and os.path.getsize(local_path) > 500:
            print(f"  -> Using cached download: {local_path}")
            return local_path

        # Folders on server: PDF is in slppdf (or slp); DOCX is in slp (or slpdocx)
        subfolders = ["slppdf", "slp"] if file_type.lower() == "pdf" else ["slp", "slpdocx"]

        for subfolder in subfolders:
            # Method 1: Try direct static file URL (instant, returns 200/404 immediately)
            direct_url = f"https://dld.srmist.edu.in/etecurricula/server/uploads/data/coordinator/{config.COURSE_CODE}/{subfolder}/{filename}"
            try:
                direct_resp = requests.get(direct_url, headers=config.HEADERS, timeout=8)
                if direct_resp.status_code == 200 and len(direct_resp.content) > 500:
                    with open(local_path, "wb") as f:
                        f.write(direct_resp.content)
                    print(f"  -> Downloaded directly from {subfolder}/: {filename} ({len(direct_resp.content)} bytes)")
                    return local_path
            except Exception:
                pass

            # Method 2: Fallback to getfile API endpoint
            payload = {
                "path": f"data/coordinator/{config.COURSE_CODE}/{subfolder}",
                "filename": filename,
                "server": "https://dld.srmist.edu.in/etecurricula/server",
                "key": "john"
            }

            try:
                resp = self.session.post(config.GET_FILE_URL, json=payload, timeout=8)
                if resp.status_code == 200 and resp.content:
                    local_path = os.path.join(config.DOWNLOAD_DIR, filename)
                    if "application/json" in resp.headers.get("Content-Type", ""):
                        try:
                            data = resp.json()
                            if isinstance(data, dict) and "result" in data:
                                file_url = data["result"].get("path", "")
                                if file_url:
                                    file_resp = requests.get(file_url, timeout=20)
                                    if file_resp.status_code == 200 and len(file_resp.content) > 100:
                                        with open(local_path, "wb") as f:
                                            f.write(file_resp.content)
                                        print(f"  -> Fetched via API: {filename}")
                                        return local_path
                            if isinstance(data, dict) and "data" in data:
                                file_bytes = base64.b64decode(data["data"])
                                with open(local_path, "wb") as f:
                                    f.write(file_bytes)
                                return local_path
                        except Exception:
                            pass
            except Exception:
                pass

        return None

    def submit_worksheet_link(self, session_id: int, slo_num: int, view_url: str, download_url: str = None) -> dict:
        """
        Submits the Google Drive/Cloud view link for a given session and SLO.
        e.g., session_id = 101, slo_num = 1 -> session_code = "1011"
        """
        if download_url is None:
            download_url = view_url

        session_code = f"{session_id}{slo_num}"
        payload = {
            "view": view_url,
            "download": download_url,
            "fileId": 0,
            "session": session_code,
            "SESSION": session_id,
            "SLO": slo_num,
            "course_code": config.COURSE_CODE,
            "course_name": config.COURSE_CODE,
            "BATCH_ID": config.BATCH_ID,
            "USER_ID": config.USER_ID,
            "FULL_NAME": config.FULL_NAME,
            "DEPARTMENT": config.DEPARTMENT
        }

        resp = self.session.post(config.SUBMIT_LINK_URL, json=payload, timeout=20)
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code, "text": resp.text}

    def submit_mcq_score(self, session_id: int, score: int = 100) -> dict:
        """
        Submits the MCQ assessment score (default 100%) for a session.
        e.g., session_id = 101
        """
        payload = {
            "key": "john",
            "session": session_id,
            "course_code": config.COURSE_CODE,
            "course_name": config.COURSE_CODE,
            "USER_ID": config.USER_ID,
            "FULL_NAME": config.FULL_NAME,
            "DEPARTMENT": config.DEPARTMENT,
            "SLOT": config.SLOTS,
            "mcq": score
        }

        resp = self.session.post(config.SUBMIT_MCQ_URL, json=payload, timeout=20)
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code, "text": resp.text}
