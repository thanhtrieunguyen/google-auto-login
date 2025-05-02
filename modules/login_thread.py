import time
import logging
import os
from PyQt5.QtCore import QThread, pyqtSignal

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from selenium.webdriver.firefox.service import Service as FirefoxService
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class LoginThread(QThread):
    login_status = pyqtSignal(str, str, str)  # email, status, message
    login_progress = pyqtSignal(int, int)  # current, total
    login_completed = pyqtSignal()
    log_message = pyqtSignal(str)
    captcha_required = pyqtSignal()
    proxy_failed = pyqtSignal()

    def __init__(self, accounts, delay=1, browser_type="chrome", start_index=0, proxy=None):
        super().__init__()
        self.accounts = accounts
        self.delay = delay
        self.browser_type = browser_type
        self.running = False
        self.driver = None
        self.current_index = start_index
        self.logger = logging.getLogger("GoogleLoginTool")
        self.headless = False
        self.captcha_event = None
        self.proxy = proxy

    def run(self):
        try:
            self.logger.info(f"Bắt đầu quá trình đăng nhập tự động với trình duyệt {self.browser_type}, delay {self.delay}s")
            self.logger.info(f"Bắt đầu quá trình đăng nhập với {len(self.accounts)} tài khoản")
            if self.current_index > 0:
                self.logger.info(f"Tiếp tục từ tài khoản thứ {self.current_index + 1}")
                self.log_message.emit(f"Tiếp tục từ tài khoản thứ {self.current_index + 1}")
            
            total_accounts = len(self.accounts)
            
            for i in range(self.current_index, len(self.accounts)):
                if not self.running:
                    break
                self.current_index = i
                self.login_progress.emit(i, total_accounts)
                try:
                    # Đảm bảo driver luôn được khởi tạo trước mỗi lần đăng nhập
                    if self.driver is None:
                        self.driver = self.create_driver(self.browser_type, self.proxy)
                    email, password = self.accounts[i]
                    self.log_message.emit(f"Xử lý tài khoản {i+1}/{total_accounts}: {email}")
                    self.logger.info(f"Xử lý tài khoản {i+1}/{total_accounts}: {email}")
                    status, message = self.login_google_account(email, password)
                    self.login_status.emit(email, status, message)
                    self.log_message.emit(f"Kết quả: {status} - {message}")
                    self.logger.info(f"Kết quả đăng nhập {email}: {status} - {message}")
                    
                    if status == "SUCCESS":
                        self.log_message.emit("Đăng nhập thành công, khởi động lại trình duyệt cho tài khoản tiếp theo...")
                        self.logger.info(f"Đóng và khởi động lại trình duyệt sau đăng nhập thành công với {email}")
                        if self.driver:
                            self.driver.quit()
                            self.driver = None
                        time.sleep(1)
                        # Không cần khởi tạo driver ở đây nữa, sẽ khởi tạo ở đầu vòng lặp
                except Exception as e:
                    error_msg = f"Lỗi khi xử lý tài khoản {self.accounts[i][0]}: {str(e)}"
                    self.login_status.emit(self.accounts[i][0], "ERROR", str(e))
                    self.log_message.emit(error_msg)
                    self.logger.error(error_msg, exc_info=True)
                for _ in range(self.delay):
                    if not self.running:
                        break
                    time.sleep(1)
        
        except Exception as e:
            error_msg = f"Lỗi hệ thống: {str(e)}"
            self.login_status.emit("SYSTEM", "ERROR", error_msg)
            self.log_message.emit(error_msg)
            self.logger.error(error_msg, exc_info=True)
        
        finally:
            if self.driver:
                self.log_message.emit("Đóng trình duyệt...")
                self.logger.info("Đóng trình duyệt")
                self.driver.quit()
            
            self.log_message.emit("Quá trình đăng nhập hoàn tất")
            self.logger.info("Quá trình đăng nhập hoàn tất")
            self.login_completed.emit()
            self.running = False

    def login_google_account(self, email, password):
        """Attempt to login to a Google account"""
        max_retry = 2
        retry_count = 0
        while retry_count <= max_retry:
            try:
                self.log_message.emit(f"Chuyển đến trang đăng nhập Google")
                self.logger.debug(f"Chuyển đến trang đăng nhập Google cho tài khoản {email}")
                
                login_url = "https://accounts.google.com/signin/v2/identifier"
                max_retries = 10
                attempt = 0
                while attempt < max_retries:
                    self.driver.get(login_url)
                    time.sleep(2)
                    page_source = self.driver.page_source
                    if (
                        "This site can’t be reached" in page_source
                        or "took too long to respond" in page_source
                        or "didn’t send any data" in page_source
                        or "<body></body>" in page_source.replace(" ", "").lower()
                        or len(page_source.strip()) < 1000
                    ):
                        self.log_message.emit(f"Trang đăng nhập Google không hoạt động, thử lại ({attempt+1}/{max_retries})...")
                        self.logger.warning(f"Trang đăng nhập Google không hoạt động (attempt {attempt+1}/{max_retries})")
                        self.driver.refresh()
                        time.sleep(2)
                        attempt += 1
                        continue

                    # --- Nhấn nút Tiếp theo đầu tiên khi chưa nhập email ---
                    try:
                        self.log_message.emit("Nhấn nút Tiếp theo đầu tiên (chưa nhập email)")
                        self.logger.debug("Nhấn nút Tiếp theo đầu tiên (chưa nhập email)")
                        first_next_btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "#identifierNext button"))
                        )
                        first_next_btn.click()
                        time.sleep(1)
                    except Exception as e:
                        self.logger.debug(f"Không nhấn được nút Tiếp theo đầu tiên: {e}")
                        # Không bắt buộc, có thể tiếp tục nếu không nhấn được

                    # --- Sau đó nhập email và nhấn Tiếp theo như bình thường ---
                    email_step_success = False
                    email_attempt = 0
                    max_email_attempts = 5
                    while email_attempt < max_email_attempts:
                        try:
                            self.log_message.emit(f"Nhập email: {email}")
                            self.logger.debug(f"Nhập email: {email}")
                            email_field = WebDriverWait(self.driver, 10).until(
                                EC.element_to_be_clickable((By.ID, "identifierId"))
                            )
                            email_field.click()
                            time.sleep(0.2)
                            email_field.clear()
                            # Dùng send_keys thay vì execute_script
                            email_field.send_keys(email)
                            self.log_message.emit("Nhấn ENTER để tiếp tục")
                            self.logger.debug("Nhấn ENTER sau khi nhập email")
                            email_field.send_keys(u'\ue007')  # ENTER key
                            email_step_success = True
                            break
                        except Exception as e:
                            self.log_message.emit(f"Không thể nhấn ENTER sau khi nhập email, reload lại trang (lần {email_attempt+1}/{max_email_attempts})...")
                            self.logger.warning(f"Không thể nhấn ENTER sau khi nhập email {email}, reload lại trang (lần {email_attempt+1}/{max_email_attempts})")
                            self.driver.refresh()
                            time.sleep(2)
                            page_source = self.driver.page_source
                            if (
                                "This site can’t be reached" in page_source
                                or "took too long to respond" in page_source
                                or "didn’t send any data" in page_source
                                or "<body></body>" in page_source.replace(" ", "").lower()
                                or len(page_source.strip()) < 1000
                            ):
                                self.log_message.emit("Sau reload bị lỗi trang trắng, reset lại số lần thử trang đăng nhập.")
                                attempt = 0
                                break
                            email_attempt += 1
                    if not email_step_success:
                        attempt += 1
                        continue
                    break
                else:
                    self.log_message.emit("Proxy failed hoặc trang đăng nhập Google không thể truy cập sau nhiều lần thử.")
                    self.proxy_failed.emit()
                    self.driver.quit()
                    self.driver = None
                    return "ERROR", "Proxy failed hoặc trang đăng nhập Google không thể truy cập"

                # Đợi trường mật khẩu xuất hiện (DOM ổn định)
                self.log_message.emit("Đợi trước khi nhập mật khẩu...")
                self.logger.debug(f"Đợi sau khi nhập email {email}")

                max_wait = 15  # seconds
                waited = 0
                while waited < max_wait:
                    if 'pwd' in self.driver.current_url:
                        break
                    time.sleep(0.5)
                    waited += 0.5
                if 'pwd' not in self.driver.current_url:
                    self.log_message.emit("Password page did not load in time.")
                    # Do not quit driver here, just return error and let main loop handle driver recreation
                    return "ERROR", "Password page did not load in time"

                try:
                    # Tìm tiêu đề popup lỗi hoặc nội dung lỗi đặc trưng
                    error_popup = None
                    try:
                        error_popup = self.driver.find_element(By.XPATH, "//h2[contains(text(),'Đã xảy ra lỗi')]")
                    except Exception:
                        # Có thể kiểm tra thêm nội dung lỗi đặc trưng
                        try:
                            error_popup = self.driver.find_element(By.XPATH, "//*[contains(text(),'Rất tiếc, đã xảy ra sự cố')]")
                        except Exception:
                            pass
                    if error_popup:
                        self.log_message.emit("Phát hiện popup lỗi Google. Đang reload lại trang và thử lại...")
                        self.logger.warning(f"Phát hiện popup lỗi Google cho {email}. Reload lại trang và thử lại (lần {retry_count+1})")
                        time.sleep(2)
                        self.driver.refresh()
                        retry_count += 1
                        continue  # Thử lại tài khoản này
                except Exception as e:
                    self.logger.debug(f"Không phát hiện popup lỗi Google: {e}")
                # --- End detect popup ---

                try:
                    captcha_found = False
                    driver = self.driver
                    
                    imgs = driver.find_elements(By.TAG_NAME, "img")
                    for img in imgs:
                        src = img.get_attribute("src")
                        if src and "/Captcha" in src:
                            self.logger.info(f"Captcha phát hiện qua img có src chứa '/Captcha': {src}")
                            captcha_found = True
                            break

                    if captcha_found:
                        self.log_message.emit("Phát hiện CAPTCHA của Google. Đang chờ người dùng giải quyết...")
                        self.logger.warning(f"Phát hiện CAPTCHA cho {email}. Chờ người dùng giải.")
                        if self.captcha_event is not None:
                            self.captcha_required.emit()
                            self.captcha_event.wait()
                            self.captcha_event.clear()
                            self.log_message.emit("Người dùng xác nhận đã giải CAPTCHA. Tiếp tục đăng nhập...")
                    else:
                        self.logger.info("Không phát hiện captcha trên trang.")
                except Exception as e:
                    self.logger.error(f"Lỗi khi kiểm tra captcha: {e}")
                    pass
                
                try:
                    error_msg_elem = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".Ekjuhf.Jj6Lae, .o6cuMc"))
                    )
                    error_text = error_msg_elem.text
                    if "Enter a valid email" in error_text or "valid email or phone number" in error_text:
                        self.logger.warning(f"Email không hợp lệ: {email} - {error_text}")
                        return "SKIPPED", f"Email không hợp lệ: {error_text}"
                except:
                    pass
                
                self.log_message.emit(f"Nhập mật khẩu")
                self.logger.debug(f"Nhập mật khẩu cho {email}")
                try:
                    password_field = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
                    )
                    password_field.click()
                    time.sleep(0.2)
                    password_field.clear()
                    # Dùng send_keys thay vì execute_script
                    password_field.send_keys(password)
                    self.log_message.emit("Nhấn ENTER để đăng nhập")
                    self.logger.debug("Nhấn ENTER sau khi nhập mật khẩu")
                    password_field.send_keys(u'\ue007')  # ENTER key
                    time.sleep(3)

                    # --- Kiểm tra nếu xuất hiện trang "Verify it’s you" ---
                    page_source = self.driver.page_source
                    if (
                        "Verify it’s you" in page_source
                        or "To help keep your account safe" in page_source
                        or "Google wants to make sure it’s really you" in page_source
                        or "help keep your account safe" in page_source
                    ):
                        self.logger.warning(f"Tài khoản {email} bị yêu cầu xác minh 'Verify it’s you', bỏ qua tài khoản này.")
                        return "SKIPPED", "Bị yêu cầu xác minh 'Verify it’s you', bỏ qua tài khoản này"

                    try:
                        wrong_password_error = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".Ly8vae.uSvLId, .o6cuMc, .Ekjuhf.Jj6Lae"))
                        )
                        error_text = wrong_password_error.text
                        if "Wrong password" in error_text or "Sai mật khẩu" in error_text:
                            self.logger.warning(f"Sai mật khẩu cho tài khoản {email}: {error_text}")
                            return "FAILED", f"Sai mật khẩu: {error_text}"
                        else:
                            self.logger.warning(f"Lỗi đăng nhập cho {email}: {error_text}")
                            return "FAILED", error_text
                    except TimeoutException:
                        pass
                    
                except TimeoutException:
                    try:
                        error_msg = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".o6cuMc, .Ekjuhf.Jj6Lae"))
                        )
                        error_text = error_msg.text
                        self.logger.warning(f"Lỗi sau khi nhập email {email}: {error_text}")
                        return "FAILED", error_text
                    except:
                        self.logger.warning(f"Không thể chuyển đến trang nhập mật khẩu cho {email}")
                        return "FAILED", "Không thể chuyển đến trang nhập mật khẩu"
                
                return_status = None
                try:
                    self.log_message.emit("Kiểm tra đăng nhập thành công")
                    WebDriverWait(self.driver, 10).until(
                        lambda driver: "myaccount.google.com" in driver.current_url or 
                                     "mail.google.com" in driver.current_url
                    )
                    self.logger.info(f"Đăng nhập thành công cho tài khoản {email}")
                    return_status = ("SUCCESS", "Đăng nhập thành công")
                except TimeoutException:
                    self.log_message.emit("Kiểm tra thông báo lỗi")
                    try:
                        error_msg = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".o6cuMc, .Ly8vae.uSvLId"))
                        )
                        self.logger.warning(f"Đăng nhập thất bại cho {email}: {error_msg.text}")
                        return_status = ("FAILED", error_msg.text)
                    except:
                        if "challenge" in self.driver.current_url or "verification" in self.driver.current_url:
                            self.logger.warning(f"Tài khoản {email} yêu cầu xác minh bổ sung")
                            return_status = ("VERIFICATION", "Yêu cầu xác minh bổ sung")
                        else:
                            self.logger.warning(f"Trạng thái đăng nhập không xác định cho {email}")
                            return_status = ("UNKNOWN", "Đã thử đăng nhập nhưng không xác định được trạng thái")
                return return_status
            except TimeoutException:
                self.logger.error(f"Timeout: các phần tử trang không tải đúng hạn cho {email}")
                return "TIMEOUT", "Các phần tử trang không tải kịp thời gian"
            except NoSuchElementException as e:
                self.logger.error(f"Không tìm thấy phần tử: {str(e)} cho {email}")
                return "ERROR", f"Không tìm thấy phần tử: {str(e)}"
            except Exception as e:
                error_str = str(e)
                # Thêm nhận diện lỗi proxy/connection refused
                if (
                    "proxy" in error_str.lower()
                    or "site can\’t be reached" in error_str.lower()
                    or "connection refused" in error_str.lower()
                    or "max retries exceeded" in error_str.lower()
                    or "failed to establish a new connection" in error_str.lower()
                ):
                    self.log_message.emit("Proxy failed or connection error. Đóng trình duyệt và yêu cầu proxy mới.")
                    self.logger.error(f"Proxy failed or connection error for {email}: {error_str}")
                    self.proxy_failed.emit()
                    if self.driver:
                        try:
                            self.driver.quit()
                        except Exception:
                            pass
                        self.driver = None
                    return "ERROR", "Proxy failed or connection error"
                if ("Đã xảy ra lỗi" in error_str or "Rất tiếc, đã xảy ra sự cố" in error_str) and retry_count < max_retry:
                    self.log_message.emit("Phát hiện lỗi hệ thống Google. Đang reload lại trang và thử lại...")
                    self.logger.warning(f"Phát hiện lỗi hệ thống Google cho {email}. Reload lại trang và thử lại (lần {retry_count+1})")
                    time.sleep(2)
                    self.driver.refresh()
                    retry_count += 1
                    continue
                self.logger.error(f"Lỗi khi đăng nhập {email}: {str(e)}", exc_info=True)
                return "ERROR", str(e)
        self.logger.error(f"Đã thử lại quá số lần cho phép với tài khoản {email} do lỗi popup Google.")
        return "ERROR", "Lỗi hệ thống Google (popup) - đã thử lại nhiều lần"
    
    def stop(self):
        self.log_message.emit("Dừng quá trình đăng nhập")
        self.logger.info(f"Dừng quá trình đăng nhập tại tài khoản thứ {self.current_index + 1}")
        self.running = False

    def create_driver(self, browser_type, proxy):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.edge.options import Options as EdgeOptions

        if browser_type == "chrome":
            options = ChromeOptions()
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')
            if self.headless:
                options.add_argument("--headless")
            self.logger.info("Khởi tạo trình duyệt Chrome")
            return webdriver.Chrome(options=options)
        elif browser_type == "firefox":
            options = FirefoxOptions()
            if proxy:
                options.set_preference("network.proxy.type", 1)
                host, port = proxy.split(":")
                options.set_preference("network.proxy.http", host)
                options.set_preference("network.proxy.http_port", int(port))
                options.set_preference("network.proxy.ssl", host)
                options.set_preference("network.proxy.ssl_port", int(port))
            if self.headless:
                options.add_argument("--headless")
            self.logger.info("Khởi tạo trình duyệt Firefox")
            gecko_driver_path = r"D:\Users\trieunth\Downloads\Compressed\geckodriver-v0.35.0-win64_2\geckodriver.exe"
            if not os.path.exists(gecko_driver_path):
                error_msg = f"Không tìm thấy geckodriver tại {gecko_driver_path}"
                self.logger.error(error_msg)
                self.log_message.emit(error_msg)
                raise FileNotFoundError(error_msg)
            service = FirefoxService(executable_path=gecko_driver_path)
            try:
                return webdriver.Firefox(service=service, options=options)
            except Exception as e:
                self.logger.error(f"Lỗi khi khởi tạo Firefox: {e}")
                self.log_message.emit(f"Lỗi khi khởi tạo Firefox: {e}")
                raise
        elif browser_type == "edge":
            options = EdgeOptions()
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')
            if self.headless:
                options.add_argument("--headless")
            self.logger.info("Khởi tạo trình duyệt Edge")
            return webdriver.Edge(options=options)
        else:
            raise ValueError("Unsupported browser type")