import sys
import csv
import time
import os
import logging
import json
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, 
                             QWidget, QLabel, QListWidget, QListWidgetItem, QMessageBox, 
                             QFileDialog, QSpinBox, QCheckBox, QProgressBar, QComboBox,
                             QTextEdit, QDialog, QDialogButtonBox, QLineEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

# Import các module đã tách
from modules.logger_util import setup_logger
from modules.dialogs import CaptchaDialog
from modules.login_thread import LoginThread, SELENIUM_AVAILABLE

# Khởi tạo logger
logger, log_file_path = setup_logger()

class GoogleLoginTool(QMainWindow):
    """Main application window for Google Login Tool"""
    
    def __init__(self):
        super().__init__()
        self.accounts = []  # List to store (email, password) tuples
        self.login_thread = None
        self.results = {}  # Dictionary to store login results
        self.checkpoint_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "login_checkpoint.json")
        self.current_csv_file = ""  # Track the current CSV file
        self.checkpoint_data = self.load_checkpoint()
        self.captcha_event = None
        
        self.init_ui()
        self.load_csv()  # Automatically load the CSV file
        
        logger.info("Ứng dụng Google Login Tool đã khởi động")
    
    def init_ui(self):
        """Set up the user interface"""
        self.setWindowTitle("Google Account Login Tool")
        self.setGeometry(100, 100, 900, 700)
        
        # Main layout
        main_layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Google Account Login Automation Tool")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(title_label)
        
        # Instructions
        instructions = """
        <b>Instructions:</b>
        1. Load accounts from CSV file (email;password format)
        2. Configure login settings below
        3. Click Start to begin automated login process
        4. Use Stop to pause the process at any time
        5. Use Resume to continue from where you left off
        6. Log messages are saved to log file for later review
        """
        instructions_label = QLabel(instructions)
        instructions_label.setStyleSheet("background-color: #f0f0f0; padding: 10px;")
        main_layout.addWidget(instructions_label)
        
        # Settings section
        settings_layout = QHBoxLayout()
        
        # File selection
        file_layout = QVBoxLayout()
        file_layout.addWidget(QLabel("Account CSV File:"))
        
        file_select_layout = QHBoxLayout()
        self.file_path_label = QLabel("mail.csv")
        file_select_layout.addWidget(self.file_path_label)
        
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_csv)
        file_select_layout.addWidget(self.browse_btn)
        
        self.reload_btn = QPushButton("Reload")
        self.reload_btn.clicked.connect(self.load_csv)
        file_select_layout.addWidget(self.reload_btn)
        
        file_layout.addLayout(file_select_layout)
        settings_layout.addLayout(file_layout)
        
        # Browser selection
        browser_layout = QVBoxLayout()
        browser_layout.addWidget(QLabel("Browser:"))
        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["Chrome", "Firefox", "Edge"])
        browser_layout.addWidget(self.browser_combo)
        settings_layout.addLayout(browser_layout)
        
        # Delay settings
        delay_layout = QVBoxLayout()
        delay_layout.addWidget(QLabel("Delay between accounts (seconds):"))
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(1, 60)
        self.delay_spinbox.setValue(5)
        delay_layout.addWidget(self.delay_spinbox)
        settings_layout.addLayout(delay_layout)
        
        # Proxy input
        proxy_layout = QVBoxLayout()
        proxy_layout.addWidget(QLabel("Proxy (host:port or user:pass@host:port):"))
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("Leave blank for no proxy")
        proxy_layout.addWidget(self.proxy_input)
        self.set_proxy_btn = QPushButton("Set Proxy")
        self.set_proxy_btn.clicked.connect(self.set_proxy)
        proxy_layout.addWidget(self.set_proxy_btn)
        settings_layout.addLayout(proxy_layout)

        main_layout.addLayout(settings_layout)
        
        # Checkpoint status
        self.checkpoint_layout = QHBoxLayout()
        self.checkpoint_label = QLabel("Checkpoint: None")
        self.checkpoint_label.setStyleSheet("color: blue; font-weight: bold;")
        self.checkpoint_layout.addWidget(self.checkpoint_label)
        
        self.clear_checkpoint_btn = QPushButton("Clear Checkpoint")
        self.clear_checkpoint_btn.clicked.connect(self.clear_checkpoint)
        self.clear_checkpoint_btn.setEnabled(False)
        self.checkpoint_layout.addWidget(self.clear_checkpoint_btn)
        
        main_layout.addLayout(self.checkpoint_layout)
        
        # Log file info
        log_layout = QHBoxLayout()
        log_layout.addWidget(QLabel("Log File:"))
        self.log_path_label = QLabel(log_file_path)
        self.log_path_label.setStyleSheet("font-weight: bold;")
        log_layout.addWidget(self.log_path_label)
        
        self.open_log_btn = QPushButton("Open Log Folder")
        self.open_log_btn.clicked.connect(self.open_log_folder)
        log_layout.addWidget(self.open_log_btn)
        
        main_layout.addLayout(log_layout)
        
        # Thêm vùng hiển thị log
        main_layout.addWidget(QLabel("Log Messages:"))
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFixedHeight(150)
        self.log_display.setStyleSheet("background-color: #f8f8f8; font-family: monospace;")
        main_layout.addWidget(self.log_display)
        
        # Account list
        main_layout.addWidget(QLabel("Accounts:"))
        self.accounts_list = QListWidget()
        self.accounts_list.setAlternatingRowColors(True)
        main_layout.addWidget(self.accounts_list)
        
        # Progress bar
        main_layout.addWidget(QLabel("Progress:"))
        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_login_process)
        button_layout.addWidget(self.start_btn)
        
        self.resume_btn = QPushButton("Resume")
        self.resume_btn.clicked.connect(self.resume_login_process)
        self.resume_btn.setEnabled(False)
        button_layout.addWidget(self.resume_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_login_process)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        button_layout.addWidget(self.export_btn)
        
        main_layout.addLayout(button_layout)
        
        # Set main widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
        
        # Check if selenium is available
        if not SELENIUM_AVAILABLE:
            error_msg = "Selenium is not installed. Please run 'pip install selenium webdriver-manager' and restart the application."
            QMessageBox.critical(self, "Missing Dependencies", error_msg)
            self.log_display.append(f"ERROR: {error_msg}")
            logger.error(error_msg)
            self.start_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)
        
        # Update checkpoint display
        self.update_checkpoint_display()
        
        # Add proxy state
        self.current_proxy = ""
        self.proxy_failed = False
    
    def load_checkpoint(self):
        """Load checkpoint data from file"""
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded checkpoint data: {data}")
                    return data
        except Exception as e:
            logger.error(f"Error loading checkpoint: {str(e)}")
        return {"file": "", "index": 0, "timestamp": ""}
    
    def save_checkpoint(self, index):
        """Save checkpoint data to file"""
        try:
            data = {
                "file": self.current_csv_file,
                "index": index,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.checkpoint_file, 'w') as f:
                json.dump(data, f)
            
            self.checkpoint_data = data
            logger.info(f"Saved checkpoint: {data}")
            return True
        except Exception as e:
            logger.error(f"Error saving checkpoint: {str(e)}")
            return False
    
    def clear_checkpoint(self):
        """Clear saved checkpoint"""
        try:
            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
            
            self.checkpoint_data = {"file": "", "index": 0, "timestamp": ""}
            self.update_checkpoint_display()
            self.resume_btn.setEnabled(False)
            self.clear_checkpoint_btn.setEnabled(False)
            
            self.log_display.append("Checkpoint đã được xóa")
            logger.info("Checkpoint đã được xóa")
            
            # Reset highlighted items in the list
            for i in range(self.accounts_list.count()):
                item = self.accounts_list.item(i)
                font = item.font()
                font.setBold(False)
                item.setFont(font)
        
        except Exception as e:
            logger.error(f"Lỗi khi xóa checkpoint: {str(e)}")
    
    def update_checkpoint_display(self):
        """Update the checkpoint display in UI"""
        if self.checkpoint_data["file"] and self.checkpoint_data["index"] > 0:
            filename = os.path.basename(self.checkpoint_data["file"])
            index = self.checkpoint_data["index"]
            timestamp = self.checkpoint_data["timestamp"]
            
            self.checkpoint_label.setText(f"Checkpoint: {filename} - Tài khoản #{index+1} - {timestamp}")
            self.clear_checkpoint_btn.setEnabled(True)
            
            # Only enable resume if the current file matches the checkpoint file
            if self.current_csv_file == self.checkpoint_data["file"]:
                self.resume_btn.setEnabled(True)
                
                # Highlight the checkpoint in the list
                if index < self.accounts_list.count():
                    item = self.accounts_list.item(index)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    self.accounts_list.scrollToItem(item)
        else:
            self.checkpoint_label.setText("Checkpoint: None")
            self.resume_btn.setEnabled(False)
            self.clear_checkpoint_btn.setEnabled(False)

    def open_log_folder(self):
        """Open the log folder in file explorer"""
        log_dir = os.path.abspath("logs")
        logger.info(f"Mở thư mục log: {log_dir}")
        
        # Mở thư mục log với lệnh hệ điều hành phù hợp
        try:
            if os.name == 'nt':  # Windows
                os.startfile(log_dir)
            elif os.name == 'posix':  # macOS, Linux
                if sys.platform == 'darwin':  # macOS
                    os.system(f'open "{log_dir}"')
                else:  # Linux
                    os.system(f'xdg-open "{log_dir}"')
            self.log_display.append(f"Đã mở thư mục log: {log_dir}")
        except Exception as e:
            error_msg = f"Không thể mở thư mục log: {str(e)}"
            self.log_display.append(f"ERROR: {error_msg}")
            logger.error(error_msg)
            QMessageBox.warning(self, "Error", error_msg)
    
    def browse_csv(self):
        """Open file dialog to select a CSV file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            self.file_path_label.setText(os.path.basename(file_path))
            self.load_csv(file_path)
            logger.info(f"Đã chọn file CSV: {file_path}")
    
    def load_csv(self, file_path=None):
        """Load accounts from CSV file"""
        if not file_path:
            # Default to mail.csv in the same directory
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mail.csv")
        
        try:
            self.accounts = []
            self.accounts_list.clear()
            self.current_csv_file = os.path.abspath(file_path)
            
            with open(file_path, 'r', encoding='utf-8-sig') as csv_file:  # Use utf-8-sig to handle BOM character
                # Try to detect if it's semicolon separated
                first_line = csv_file.readline().strip()
                csv_file.seek(0)
                
                if ';' in first_line:
                    reader = csv.reader(csv_file, delimiter=';')
                else:
                    reader = csv.reader(csv_file)
                
                for row in reader:
                    if len(row) >= 2:
                        email = row[0].strip()
                        password = row[1].strip()
                        self.accounts.append((email, password))
                        self.accounts_list.addItem(f"{email} - {'*' * len(password)}")
            
            self.status_label.setText(f"Loaded {len(self.accounts)} accounts from CSV")
            self.progress_bar.setMaximum(len(self.accounts))
            self.progress_bar.setValue(0)
            
            log_msg = f"Đã tải {len(self.accounts)} tài khoản từ {file_path}"
            self.log_display.append(log_msg)
            logger.info(log_msg)
            
            # Check if this file matches our checkpoint
            self.update_checkpoint_display()
            
        except Exception as e:
            error_msg = f"Failed to load CSV file: {str(e)}"
            QMessageBox.critical(self, "Error", error_msg)
            self.log_display.append(f"ERROR: {error_msg}")
            logger.error(error_msg, exc_info=True)
    
    def start_login_process(self):
        """Start the automated login process from the beginning"""
        if not self.accounts:
            msg = "Không có tài khoản nào được tải. Vui lòng tải file CSV trước."
            QMessageBox.warning(self, "No Accounts", msg)
            self.log_display.append(f"WARNING: {msg}")
            logger.warning(msg)
            return
            
        if self.login_thread and self.login_thread.isRunning():
            msg = "Quá trình đăng nhập đang chạy."
            QMessageBox.warning(self, "Process Running", msg)
            self.log_display.append(f"WARNING: {msg}")
            logger.warning(msg)
            return
        
        # Get settings
        delay = self.delay_spinbox.value()
        browser_type = self.browser_combo.currentText().lower()
        proxy = self.current_proxy
        
        # Create login thread starting from the beginning
        self.login_thread = LoginThread(self.accounts, delay, browser_type, start_index=0, proxy=proxy)
        self.login_thread.login_status.connect(self.update_login_status)
        self.login_thread.login_progress.connect(self.update_progress)
        self.login_thread.login_completed.connect(self.login_process_completed)
        self.login_thread.log_message.connect(self.add_log_message)
        self.login_thread.captcha_required.connect(self.handle_captcha_required)
        self.login_thread.proxy_failed.connect(self.handle_proxy_failed)
        self.login_thread.captcha_event = self.get_captcha_event()
        
        # Set thread as running
        self.login_thread.running = True
        
        # Start thread
        self.login_thread.start()
        
        # Update UI
        self.status_label.setText("Login process started...")
        self.start_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.browse_btn.setEnabled(False)
        self.reload_btn.setEnabled(False)
        self.clear_checkpoint_btn.setEnabled(False)
        
        logger.info(f"Bắt đầu quá trình đăng nhập tự động với trình duyệt {browser_type}, delay {delay}s")
    
    def resume_login_process(self):
        """Resume the login process from the checkpoint"""
        if not self.accounts:
            msg = "Không có tài khoản nào được tải. Vui lòng tải file CSV trước."
            QMessageBox.warning(self, "No Accounts", msg)
            self.log_display.append(f"WARNING: {msg}")
            logger.warning(msg)
            return
            
        if self.login_thread and self.login_thread.isRunning():
            msg = "Quá trình đăng nhập đang chạy."
            QMessageBox.warning(self, "Process Running", msg)
            self.log_display.append(f"WARNING: {msg}")
            logger.warning(msg)
            return
        
        # Check if we have a valid checkpoint
        if not self.checkpoint_data["file"] or self.checkpoint_data["index"] <= 0:
            msg = "Không tìm thấy checkpoint để tiếp tục."
            QMessageBox.warning(self, "No Checkpoint", msg)
            self.log_display.append(f"WARNING: {msg}")
            logger.warning(msg)
            return
            
        # Check if the current file matches the checkpoint
        if self.current_csv_file != self.checkpoint_data["file"]:
            msg = f"File CSV hiện tại khác với file trong checkpoint. Vui lòng tải file {os.path.basename(self.checkpoint_data['file'])}."
            QMessageBox.warning(self, "File Mismatch", msg)
            self.log_display.append(f"WARNING: {msg}")
            logger.warning(msg)
            return
        
        start_index = self.checkpoint_data["index"]
        
        # Get settings
        delay = self.delay_spinbox.value()
        browser_type = self.browser_combo.currentText().lower()
        proxy = self.current_proxy
        
        # Create login thread starting from the checkpoint
        self.login_thread = LoginThread(self.accounts, delay, browser_type, start_index=start_index, proxy=proxy)
        self.login_thread.login_status.connect(self.update_login_status)
        self.login_thread.login_progress.connect(self.update_progress)
        self.login_thread.login_completed.connect(self.login_process_completed)
        self.login_thread.log_message.connect(self.add_log_message)
        self.login_thread.captcha_required.connect(self.handle_captcha_required)
        self.login_thread.proxy_failed.connect(self.handle_proxy_failed)
        self.login_thread.captcha_event = self.get_captcha_event()
        
        # Set thread as running
        self.login_thread.running = True
        
        # Start thread
        self.login_thread.start()
        
        # Update UI
        self.status_label.setText(f"Tiếp tục quá trình đăng nhập từ tài khoản #{start_index + 1}...")
        self.start_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.browse_btn.setEnabled(False)
        self.reload_btn.setEnabled(False)
        self.clear_checkpoint_btn.setEnabled(False)
        
        logger.info(f"Tiếp tục quá trình đăng nhập từ tài khoản #{start_index + 1} với trình duyệt {browser_type}, delay {delay}s")
    
    def stop_login_process(self):
        """Stop the automated login process"""
        if self.login_thread and self.login_thread.isRunning():
            # Save checkpoint before stopping
            current_index = self.login_thread.current_index
            if current_index >= 0:
                if self.save_checkpoint(current_index):
                    self.log_display.append(f"Đã lưu checkpoint tại tài khoản #{current_index + 1}")
            
            self.login_thread.stop()
            self.status_label.setText("Stopping login process...")
            self.log_display.append("Đang dừng quá trình đăng nhập...")
            logger.info("Người dùng đã yêu cầu dừng quá trình đăng nhập")
    
    def add_log_message(self, message):
        """Add message to the log display"""
        self.log_display.append(message)
        # Tự động cuộn xuống để hiển thị tin nhắn mới nhất
        self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())
    
    def update_login_status(self, email, status, message):
        """Update the status of an account login attempt"""
        # Find the item in the list
        for i in range(self.accounts_list.count()):
            item = self.accounts_list.item(i)
            if item.text().startswith(email):
                # Update the item text with status
                status_color_map = {
                    "SUCCESS": Qt.green,
                    "FAILED": Qt.red,
                    "ERROR": Qt.red,
                    "TIMEOUT": Qt.yellow,
                    "VERIFICATION": Qt.blue,
                    "UNKNOWN": Qt.gray,
                    "SKIPPED": Qt.cyan
                }
                
                item.setText(f"{email} - {status} - {message}")
                
                # Use direct Qt color constants instead of trying to access them by name
                color = status_color_map.get(status, Qt.black)
                item.setForeground(color)
                break
        
        # Store results
        self.results[email] = {"status": status, "message": message, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    
    def update_progress(self, current, total):
        """Update the progress bar"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Processing account {current + 1} of {total}")
    
    def login_process_completed(self):
        """Handle completion of the login process"""
        self.status_label.setText("Login process completed")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.browse_btn.setEnabled(True)
        self.reload_btn.setEnabled(True)
        self.clear_checkpoint_btn.setEnabled(self.checkpoint_data["file"] != "")
        
        # Clear checkpoint if process completed successfully
        if self.login_thread and self.login_thread.current_index >= len(self.accounts) - 1:
            self.clear_checkpoint()
        else:
            self.update_checkpoint_display()
        
        # Show summary
        total = len(self.results)
        success = sum(1 for result in self.results.values() if result["status"] == "SUCCESS")
        skipped = sum(1 for result in self.results.values() if result["status"] == "SKIPPED")
        failed = total - success - skipped
        
        summary = f"Quá trình đăng nhập hoàn tất\nTổng số tài khoản: {total}\nThành công: {success}\nBỏ qua (email không hợp lệ): {skipped}\nThất bại: {failed}"
        self.log_display.append(summary)
        logger.info(summary)
        
        QMessageBox.information(
            self,
            "Login Process Completed",
            summary
        )
    
    def export_results(self):
        """Export login results to a CSV file"""
        if not self.results:
            msg = "Không có kết quả đăng nhập để xuất."
            QMessageBox.warning(self, "No Results", msg)
            self.log_display.append(f"WARNING: {msg}")
            logger.warning(msg)
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Results", f"login_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
                    writer = csv.writer(csv_file, delimiter=';')
                    writer.writerow(["Email", "Status", "Message", "Timestamp"])
                    
                    for email, result in self.results.items():
                        writer.writerow([
                            email,
                            result["status"],
                            result["message"],
                            result["timestamp"]
                        ])
                
                msg = f"Kết quả đã được xuất ra {file_path}"
                QMessageBox.information(self, "Export Successful", msg)
                self.log_display.append(msg)
                logger.info(f"Đã xuất kết quả đăng nhập ra file: {file_path}")
            
            except Exception as e:
                error_msg = f"Failed to export results: {str(e)}"
                QMessageBox.critical(self, "Export Error", error_msg)
                self.log_display.append(f"ERROR: {error_msg}")
                logger.error(error_msg, exc_info=True)

    def get_captcha_event(self):
        # Tạo threading.Event để đồng bộ giải captcha
        import threading
        if not self.captcha_event:
            self.captcha_event = threading.Event()
        return self.captcha_event

    def handle_captcha_required(self):
        # Hiện dialog yêu cầu người dùng giải captcha
        dlg = CaptchaDialog(self)
        dlg.exec_()
        # Khi người dùng nhấn OK, giải phóng event để thread tiếp tục
        if self.captcha_event:
            self.captcha_event.set()

    def set_proxy(self):
        """Set the proxy from user input"""
        proxy = self.proxy_input.text().strip()
        self.current_proxy = proxy
        self.proxy_failed = False
        self.log_display.append(f"Proxy set to: {proxy if proxy else 'No proxy'}")
        logger.info(f"Proxy set to: {proxy if proxy else 'No proxy'}")

    def handle_proxy_failed(self):
        """Handle proxy failure: pause and prompt user to enter a new proxy"""
        self.proxy_failed = True
        self.status_label.setText("Proxy failed. Please enter a new proxy and click Set Proxy, then Resume.")
        self.log_display.append("Proxy failed. Please enter a new proxy and click Set Proxy, then Resume.")
        logger.warning("Proxy failed. Waiting for user to set a new proxy.")
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.resume_btn.setEnabled(True)
        self.set_proxy_btn.setEnabled(True)
        QMessageBox.warning(self, "Proxy Failed", "Proxy failed. Please enter a new proxy and click Set Proxy, then Resume.")


def main():
    # Thông báo khởi động ứng dụng
    logger.info("=== Khởi động Google Login Tool ===")
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for a consistent look across platforms
    window = GoogleLoginTool()
    window.show()
    
    # Xử lý khi thoát ứng dụng
    exit_code = app.exec_()
    logger.info("=== Kết thúc Google Login Tool ===")
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.critical(f"Lỗi nghiêm trọng: {str(e)}", exc_info=True)
        raise
