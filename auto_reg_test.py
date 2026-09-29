import os
import re
import time
import json
import random
import string
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

GPM_API_BASE = "http://127.0.0.1:9495/api/v1"
TINYHOST_API_BASE = "https://tinyhost.shop"
PROFILE_ID = "219bf4f0-6275-499f-b1ea-7a1ef607e6ee" # Hermes Pilot - Supadata

class TinyHostMailAPI:
    def __init__(self, base_url=TINYHOST_API_BASE):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def get_clean_domain(self) -> str:
        url = f"{self.base_url}/api/random-domains/?limit=10"
        try:
            res = self.session.get(url, timeout=10).json()
            domains = res.get("domains", [])
            valid_domains = [d.rstrip(".") for d in domains if d and "." in d and not d.endswith("infinityfreeapp.com.")]
            if valid_domains:
                # Ưu tiên các domain ngắn gọn
                chosen = random.choice(valid_domains)
                print(f"[TinyHost] Chọn domain: {chosen}")
                return chosen
        except Exception as e:
            print(f"[TinyHost] Lỗi lấy domain: {e}")
        return "graphicmen.site"

    def create_mailbox(self):
        domain = self.get_clean_domain()
        user = "dev" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        email = f"{user}@{domain}"
        return user, domain, email

    def wait_for_email_or_otp(self, domain: str, user: str, timeout: int = 120):
        start = time.time()
        print(f"[TinyHost] Bắt đầu lắng nghe hộp thư {user}@{domain} (Timeout {timeout}s)...")
        while time.time() - start < timeout:
            try:
                url = f"{self.base_url}/api/email/{domain}/{user}/"
                res = self.session.get(url, params={"page": 1, "limit": 5}, timeout=10).json()
                emails = res.get("emails", [])
                if emails:
                    print(f"[TinyHost] Nhận được {len(emails)} email mới!")
                    mail = emails[0]
                    subject = mail.get("subject", "")
                    body = mail.get("body", "")
                    html_body = mail.get("html_body", "")
                    full_text = f"{subject}\n{body}\n{html_body}"
                    print(f"[TinyHost] Tiêu đề: '{subject}'")

                    # 1. Tìm mã OTP số 6 chữ số
                    otp_match = re.search(r'\b(\d{6})\b', full_text)
                    otp = otp_match.group(1) if otp_match else None

                    # 2. Tìm link xác nhận (nếu Supadata dùng magic link / verify link)
                    link_match = re.search(r'https://dash\.supadata\.ai[^\s"\'<>]+', full_text)
                    verify_link = link_match.group(0) if link_match else None

                    return {
                        "subject": subject,
                        "otp": otp,
                        "verify_link": verify_link,
                        "full_text": full_text
                    }
            except Exception as e:
                print(f"[TinyHost] Lỗi check inbox: {e}")
            time.sleep(4)
        print("[TinyHost] Hết thời gian chờ nhận email.")
        return None

def start_gpm_profile(profile_id):
    url = f"{GPM_API_BASE}/profiles/start/{profile_id}"
    print(f"[GPM] Khởi động profile {profile_id}...")
    res = requests.get(url, timeout=30).json()
    if not res.get("success"):
        raise Exception(f"Không thể start GPM profile: {res}")
    data = res.get("data", {})
    driver_path = data.get("driver_path")
    port = data.get("remote_debugging_port")
    remote_address = f"127.0.0.1:{port}"
    print(f"[GPM] Profile khởi động thành công: Driver={driver_path}, Port={port}")
    return driver_path, remote_address

def stop_gpm_profile(profile_id):
    url = f"{GPM_API_BASE}/profiles/stop/{profile_id}"
    try:
        requests.get(url, timeout=10)
        print(f"[GPM] Đã đóng profile {profile_id}")
    except Exception as e:
        print(f"[GPM] Lỗi đóng profile: {e}")

def run_test():
    driver_path, remote_address = start_gpm_profile(PROFILE_ID)
    
    options = Options()
    options.add_experimental_option("debuggerAddress", remote_address)
    service = Service(executable_path=driver_path)
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    wait = WebDriverWait(driver, 20)

    try:
        mail_api = TinyHostMailAPI()
        user, domain, email = mail_api.create_mailbox()
        full_name = "Dev " + "".join(random.choices(string.ascii_uppercase, k=1)) + "".join(random.choices(string.ascii_lowercase, k=4))

        print(f"\n[SUPADATA] Chuẩn bị đăng ký tài khoản:")
        print(f"  - Name:  {full_name}")
        print(f"  - Email: {email}\n")

        print("[SUPADATA] Mở trang sign-up...")
        driver.get("https://dash.supadata.ai/auth/sign-up")
        time.sleep(3)

        print("[SUPADATA] Nhập Name và Email...")
        # Tìm input name
        name_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='name' or @placeholder='Name' or @type='text']")))
        name_input.clear()
        name_input.send_keys(full_name)

        # Tìm input email
        email_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='email' or @placeholder='Email' or @type='email']")))
        email_input.clear()
        email_input.send_keys(email)
        time.sleep(1)

        print("[SUPADATA] Xử lý Cloudflare Turnstile Captcha...")
        # Kiểm tra xem Turnstile có trong iframe không
        time.sleep(3)
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        turnstile_iframe = None
        for f in iframes:
            src = f.get_attribute("src") or ""
            title = f.get_attribute("title") or ""
            if "cloudflare" in src or "challenges.cloudflare.com" in src or "security challenge" in title.lower():
                turnstile_iframe = f
                break
        
        if turnstile_iframe:
            print("[SUPADATA] Tìm thấy Turnstile iframe. Đang kiểm tra trạng thái checkbox...")
            try:
                driver.switch_to.frame(turnstile_iframe)
                checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox'] | //label")
                if checkboxes:
                    print("[SUPADATA] Click vào Turnstile checkbox...")
                    checkboxes[0].click()
                driver.switch_to.default_content()
            except Exception as ex:
                print(f"[SUPADATA] Turnstile auto-solve hoặc error: {ex}")
                driver.switch_to.default_content()

        time.sleep(4)

        print("[SUPADATA] Click nút 'Create account'...")
        create_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Create account')]")))
        create_btn.click()
        print("[SUPADATA] Đã click nút Create account!")

        time.sleep(4)

        # Chờ email gửi về
        mail_res = mail_api.wait_for_email_or_otp(domain, user, timeout=90)
        if not mail_res:
            print("[SUPADATA] [FAILED] Không nhận được email từ Supadata!")
            driver.save_screenshot("supadata_no_mail.png")
            return False

        print(f"[SUPADATA] Chi tiết email nhận được: {mail_res}")

        if mail_res.get("otp"):
            otp_code = mail_res["otp"]
            print(f"[SUPADATA] Nhập mã OTP: {otp_code}")
            time.sleep(2)
            
            # Thử tìm ô nhập OTP (dạng multiple inputs hoặc 1 input)
            otp_inputs = driver.find_elements(By.XPATH, "//input[contains(@class, 'otp') or @maxlength='1']")
            if len(otp_inputs) >= 6:
                for i, ch in enumerate(otp_code):
                    otp_inputs[i].send_keys(ch)
            else:
                main_otp = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text' or @type='number' or @placeholder='Code' or @placeholder='OTP']")))
                main_otp.send_keys(otp_code)

            # Bấm nút xác nhận nếu có
            time.sleep(2)
            confirm_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Verify') or contains(., 'Continue') or contains(., 'Submit')]")
            if confirm_btns:
                confirm_btns[0].click()

        elif mail_res.get("verify_link"):
            print(f"[SUPADATA] Mở link xác thực: {mail_res['verify_link']}")
            driver.get(mail_res["verify_link"])

        time.sleep(8)
        print(f"[SUPADATA] URL hiện tại: {driver.current_url}")
        print(f"[SUPADATA] Title hiện tại: {driver.title}")

        # Lưu lại tài khoản đăng ký thành công
        with open("registered_accounts_success.txt", "a", encoding="utf-8") as f:
            f.write(f"{email}|{full_name}|{driver.current_url}\n")
        print("[SUPADATA] [SUCCESS] Đã hoàn thành quy trình đăng ký tài khoản!")

        return True

    except Exception as e:
        print(f"[!] Lỗi trong quá trình chạy: {e}")
        try:
            driver.save_screenshot("supadata_error.png")
        except:
            pass
        return False
    finally:
        # Không thoát driver để anh có thể quan sát, hoặc đóng GPM nếu muốn
        print("[*] Kết thúc phiên test.")

if __name__ == "__main__":
    run_test()
