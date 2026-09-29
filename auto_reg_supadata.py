import os
import re
import time
import json
import random
import string
import datetime
import subprocess
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==================== CẤU HÌNH HỆ THỐNG ====================
GPM_API_BASE = "http://127.0.0.1:9495/api/v1"
TINYHOST_API_BASE = "https://tinyhost.shop"
OUTPUT_FILE = "registered_supadata_accounts.txt"

# ==================== 1. TINYHOST MAIL API ====================
class TinyHostMailAPI:
    """Quản lý tạo email tạm và đọc thư / OTP từ TinyHost API"""
    def __init__(self, base_url=TINYHOST_API_BASE):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def get_online_domain(self) -> str:
        url = f"{self.base_url}/api/random-domains/?limit=10"
        try:
            res = self.session.get(url, timeout=10).json()
            domains = res.get("domains", [])
            valid_domains = [d.rstrip(".") for d in domains if d and "." in d and not d.endswith("infinityfreeapp.com.")]
            if valid_domains:
                chosen = random.choice(valid_domains)
                return chosen
        except Exception as e:
            print(f"[TinyHost] Lỗi khi lấy domain: {e}")
        return "graphicmen.site"

    def create_mailbox(self):
        domain = self.get_online_domain()
        user = "dev" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        email = f"{user}@{domain}"
        return user, domain, email

    def wait_for_verification(self, domain: str, user: str, timeout: int = 120):
        start = time.time()
        print(f"[TinyHost] Đang lắng nghe thư đến hòm: {user}@{domain} (Timeout {timeout}s)...")
        while time.time() - start < timeout:
            try:
                url = f"{self.base_url}/api/email/{domain}/{user}/"
                res = self.session.get(url, params={"page": 1, "limit": 5}, timeout=10).json()
                emails = res.get("emails", [])
                if emails:
                    mail = emails[0]
                    subject = mail.get("subject", "")
                    body = mail.get("body", "")
                    html_body = mail.get("html_body", "")
                    full_content = f"{subject}\n{body}\n{html_body}"
                    print(f"[TinyHost] Nhận được thư: '{subject}'")

                    # Tìm direct link xác nhận email
                    verify_link_match = re.search(r'https://dash\.supadata\.ai/auth/verify-email/request/[a-zA-Z0-9]+', full_content)
                    # Tìm callback magic link (nếu đăng nhập)
                    magic_link_match = re.search(r'https://dash\.supadata\.ai/api/auth/callback/resend\?[^\s"\'<>]+', full_content)
                    
                    # Tìm OTP dạng chữ số hoặc chữ số kèm ký tự
                    otp_match = re.search(r'<strong>([A-Z0-9]{6})</strong>', full_content)
                    if not otp_match:
                        otp_match = re.search(r'(?:one-time password|code is|mã là)[^\w]*([A-Z0-9]{6})', full_content, re.IGNORECASE)

                    return {
                        "subject": subject,
                        "verify_link": verify_link_match.group(0) if verify_link_match else None,
                        "magic_link": magic_link_match.group(0) if magic_link_match else None,
                        "otp": otp_match.group(1) if otp_match else None
                    }
            except Exception as e:
                print(f"[TinyHost] Đang đợi email: {e}")
            time.sleep(4)
        return None

# ==================== 2. GPM-LOGIN CONTROLLER ====================
class GPMController:
    """Quản lý Profile GPMLogin qua Local REST API v1"""
    def __init__(self, base_url=GPM_API_BASE):
        self.base_url = base_url.rstrip("/")

    def get_all_profiles(self):
        url = f"{self.base_url}/profiles"
        try:
            res = requests.get(url, timeout=10).json()
            return res.get("data", {}).get("data", [])
        except Exception as e:
            print(f"[GPM] Lỗi lấy danh sách profile: {e}")
            return []

    def start_profile(self, profile_id: str):
        url = f"{self.base_url}/profiles/start/{profile_id}"
        print(f"[GPM] Khởi động Profile ID: {profile_id}...")
        res = requests.get(url, timeout=30).json()
        if not res.get("success"):
            raise Exception(f"GPM start thất bại: {res}")
        data = res.get("data", {})
        driver_path = data.get("driver_path")
        port = data.get("remote_debugging_port")
        remote_address = f"127.0.0.1:{port}"
        print(f"[GPM] Khởi động thành công! Port: {port}")
        return driver_path, remote_address

    def stop_profile(self, profile_id: str):
        url = f"{self.base_url}/profiles/stop/{profile_id}"
        try:
            requests.get(url, timeout=10)
            print(f"[GPM] Đã đóng profile {profile_id}")
        except Exception as e:
            print(f"[GPM] Lỗi đóng profile: {e}")

# ==================== 3. SUPADATA REGISTRATION WORKER ====================
def register_supadata_single_profile(driver_path: str, remote_address: str, profile_id: str):
    options = Options()
    options.add_experimental_option("debuggerAddress", remote_address)
    service = Service(executable_path=driver_path)
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(35)
    wait = WebDriverWait(driver, 20)

    # Đảm bảo chuyển sang tab trình duyệt chính (tránh tab extension ngầm)
    for h in driver.window_handles:
        driver.switch_to.window(h)
        if driver.current_url.startswith("http"):
            break

    mail_api = TinyHostMailAPI()
    user, domain, email = mail_api.create_mailbox()
    full_name = "Dev " + "".join(random.choices(string.ascii_uppercase, k=1)) + "".join(random.choices(string.ascii_lowercase, k=5))

    print(f"\n=======================================================")
    print(f"[*] Bắt đầu đăng ký tài khoản:")
    print(f"    - Email:   {email}")
    print(f"    - Name:    {full_name}")
    print(f"    - Profile: {profile_id}")
    print(f"=======================================================")

    # 1. Mở trang Sign-up
    driver.get("https://dash.supadata.ai/auth/sign-up")
    time.sleep(3)

    # 2. Điền Form
    name_el = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Name' or @name='name' or @type='text']")))
    name_el.clear()
    name_el.send_keys(full_name)

    email_el = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Email' or @name='email' or @type='email']")))
    email_el.clear()
    email_el.send_keys(email)
    time.sleep(1)

    # 3. Chờ Turnstile Cloudflare Captcha
    print("[*] Xử lý Turnstile Captcha...")
    time.sleep(3)
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for f in iframes:
        src = f.get_attribute("src") or ""
        title = f.get_attribute("title") or ""
        if "cloudflare" in src or "challenges.cloudflare.com" in src or "security challenge" in title.lower():
            try:
                driver.switch_to.frame(f)
                chk = driver.find_elements(By.XPATH, "//input[@type='checkbox'] | //label")
                if chk:
                    chk[0].click()
                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()
            break
    time.sleep(3)

    # 4. Click Create account
    create_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Create account')]")))
    driver.execute_script("arguments[0].click();", create_btn)
    print("[+] Đã bấm 'Create account'. Chờ email xác thực gửi về...")
    time.sleep(4)

    # 5. Chờ email từ TinyHost
    mail_data = mail_api.wait_for_verification(domain, user, timeout=120)
    if not mail_data:
        print("[-] [FAILED] Không nhận được email xác thực từ Supadata.")
        return False, None

    # 6. Xác nhận tài khoản
    if mail_data.get("verify_link"):
        print(f"[+] Kích hoạt tài khoản qua Verify Link: {mail_data['verify_link']}")
        driver.get(mail_data["verify_link"])
        time.sleep(5)
    elif mail_data.get("otp"):
        otp_code = mail_data["otp"]
        print(f"[+] Nhập mã OTP: {otp_code}")
        otp_inputs = driver.find_elements(By.XPATH, "//input[contains(@class, 'otp') or @maxlength='1']")
        if len(otp_inputs) >= len(otp_code):
            for i, ch in enumerate(otp_code):
                otp_inputs[i].send_keys(ch)
        else:
            main_inp = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text' or @placeholder='Code' or @placeholder='OTP']")))
            main_inp.send_keys(otp_code)
        time.sleep(3)

    # 7. Đăng nhập nếu đang ở trang verify-email/success
    if "verify-email" in driver.current_url or "success" in driver.current_url:
        print("[*] Đang thực hiện đăng nhập vào Dashboard...")
        driver.get("https://dash.supadata.ai/auth/sign-in")
        time.sleep(3)
        sign_email_el = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Email' or @type='email']")))
        sign_email_el.clear()
        sign_email_el.send_keys(email)
        signin_btn = driver.find_element(By.XPATH, "//button[contains(., 'Sign in')]")
        driver.execute_script("arguments[0].click();", signin_btn)
        print("[+] Đã gửi yêu cầu Magic Link đăng nhập...")

        # Chờ nhận Magic Link
        time.sleep(6)
        login_mail = mail_api.wait_for_verification(domain, user, timeout=60)
        if login_mail and login_mail.get("magic_link"):
            print(f"[+] Truy cập Magic Link: {login_mail['magic_link']}")
            driver.get(login_mail["magic_link"])
            time.sleep(6)

    # 8. Xử lý Onboarding Survey (nếu có)
    time.sleep(3)
    if "api-key-test" in driver.current_url or "organizations" in driver.current_url:
        print("[*] Vượt qua bước khảo sát Onboarding...")
        labels = driver.find_elements(By.TAG_NAME, "label")
        for l in labels:
            if "Google" in l.text or "AI assistant" in l.text or "YouTube" in l.text:
                try: driver.execute_script("arguments[0].click();", l)
                except: pass
                break
        time.sleep(1)
        cont_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Continue')]")
        for cb in cont_btns:
            try: driver.execute_script("arguments[0].click();", cb)
            except: pass
        time.sleep(3)

        # Chuyển vào Dashboard
        dash_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Go to dashboard')]")
        for db in dash_btns:
            try: driver.execute_script("arguments[0].click();", db)
            except: pass
        time.sleep(4)

    # 9. Lấy API Key từ Dashboard
    api_key = "NOT_EXTRACTED"
    try:
        # Điều hướng sang trang API Keys
        current_url = driver.current_url
        if "organizations" in current_url:
            org_id = current_url.split("/organizations/")[1].split("/")[0]
            driver.get(f"https://dash.supadata.ai/organizations/{org_id}/api-key")
            time.sleep(4)
        
        # Click nút Copy API Key
        copy_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Copy API key') or contains(@aria-label, 'Copy')]")
        if copy_btns:
            driver.execute_script("arguments[0].click();", copy_btns[0])
            time.sleep(1)
            try:
                # Đọc từ Clipboard hệ thống
                copied_key = subprocess.check_output(["powershell", "-Command", "Get-Clipboard"]).decode("utf-8").strip()
                if copied_key.startswith("sd_"):
                    api_key = copied_key
            except Exception:
                pass
    except Exception as ex:
        print(f"[!] Lỗi khi lấy API key: {ex}")

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = f"{email}|{full_name}|{api_key}|{profile_id}|{now_str}\n"

    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(record)

    print(f"\n[SUCCESS] >>> ĐĂNG KÝ THÀNH CÔNG: {record.strip()} <<<")
    return True, api_key

# ==================== 4. BATCH RUNNER (CHẠY TOÀN BỘ) ====================
def run_auto_reg_pipeline(profile_ids: list):
    gpm = GPMController()
    total = len(profile_ids)
    print(f"\n=======================================================")
    print(f"   BẮT ĐẦU PIPELINE AUTO REG CHO {total} PROFILE GPM")
    print(f"=======================================================\n")

    for idx, pid in enumerate(profile_ids):
        print(f"\n>>>>> TIẾN HÀNH PROFILE [{idx+1}/{total}]: {pid} <<<<<")
        try:
            driver_path, remote_address = gpm.start_profile(pid)
            success, api_key = register_supadata_single_profile(driver_path, remote_address, pid)
        except Exception as e:
            print(f"[-] Lỗi trong profile {pid}: {e}")
        finally:
            gpm.stop_profile(pid)
            print(f"[*] Đã đóng profile {pid}. Nghỉ 5s...")
            time.sleep(5)

    print("\n=======================================================")
    print(f"   HOÀN TẤT PIPELINE! KẾT QUẢ ĐÃ LƯU TẠI: {OUTPUT_FILE}")
    print(f"=======================================================\n")

if __name__ == "__main__":
    # Điền danh sách các profile ID cần reg:
    TARGET_PROFILES = [
        "219bf4f0-6275-499f-b1ea-7a1ef607e6ee", # Hermes Pilot - Supadata
    ]
    run_auto_reg_pipeline(TARGET_PROFILES)
