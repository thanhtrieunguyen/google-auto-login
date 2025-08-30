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
                             QTextEdit, QDialog, QDialogButtonBox, QLineEdit, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor

# Import các module đã tách
from modules.logger_util import setup_logger
from modules.dialogs import CaptchaDialog
from modules.login_thread import LoginThread, SELENIUM_AVAILABLE
from modules.network_usage import NetworkUsageMonitor

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
        self.network_usage_label = None  # Sẽ khởi tạo trong init_ui
        
        self.init_ui()
        self.load_csv()  # Automatically load the CSV file
        
        logger.info("Ứng dụng Google Login Tool đã khởi động")
    
    def init_ui(self):
        """Set up the user interface"""
        self.setWindowTitle("Tự động đăng nhập Google")
        self.setGeometry(50, 50, 1000, 800)
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333333;
                font-size: 12px;
            }
            QPushButton {
                background-color: #4285f4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QPushButton#stopButton {
                background-color: #ea4335;
            }
            QPushButton#stopButton:hover {
                background-color: #d33426;
            }
            QPushButton#exportButton {
                background-color: #34a853;
            }
            QPushButton#exportButton:hover {
                background-color: #2d9249;
            }
            QLineEdit, QComboBox, QSpinBox {
                padding: 6px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                background-color: #f8f8f8;
            }
            QProgressBar::chunk {
                background-color: #4285f4;
                border-radius: 3px;
            }
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                font-family: 'Consolas', monospace;
            }
        """)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title section
        title_frame = QFrame()
        title_frame.setStyleSheet("""
            QFrame {
                background-color: #4285f4;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        title_layout = QVBoxLayout()
        title_label = QLabel("Tự động đăng nhập Google")
        title_layout.addWidget(title_label)
        title_frame.setLayout(title_layout)
        main_layout.addWidget(title_frame)
        
        # Settings section
        settings_frame = QFrame()
        settings_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(20)
        
        # File selection
        file_layout = QVBoxLayout()
        file_layout.addWidget(QLabel("<b>File tài khoản CSV:</b>"))
        
        file_select_layout = QHBoxLayout()
        self.file_path_label = QLabel("mail.csv")
        self.file_path_label.setStyleSheet("color: #666;")
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
        browser_layout.addWidget(QLabel("<b>Browser:</b>"))
        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["Chrome", "Firefox", "Edge"])
        browser_layout.addWidget(self.browser_combo)
        settings_layout.addLayout(browser_layout)
        
        # Delay settings
        delay_layout = QVBoxLayout()
        delay_layout.addWidget(QLabel("<b>Khoảng thời gian giữa các tài khoản (giây):</b>"))
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(1, 60)
        self.delay_spinbox.setValue(5)
        delay_layout.addWidget(self.delay_spinbox)
        settings_layout.addLayout(delay_layout)
        
        # Proxy input
        proxy_layout = QVBoxLayout()
        proxy_layout.addWidget(QLabel("<b>Proxy (host:port or user:pass@host:port):</b>"))
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("Để trống nếu không sử dụng proxy")
        proxy_layout.addWidget(self.proxy_input)
        self.set_proxy_btn = QPushButton("Đặt Proxy")
        self.set_proxy_btn.clicked.connect(self.set_proxy)
        proxy_layout.addWidget(self.set_proxy_btn)
        settings_layout.addLayout(proxy_layout)

        settings_frame.setLayout(settings_layout)
        main_layout.addWidget(settings_frame)
        
        # Checkpoint status
        checkpoint_frame = QFrame()
        checkpoint_frame.setStyleSheet("""
            QFrame {
                background-color: #e8f0fe;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        self.checkpoint_layout = QHBoxLayout()
        self.checkpoint_label = QLabel("Checkpoint: None")
        self.checkpoint_label.setStyleSheet("color: #1a73e8; font-weight: bold;")
        self.checkpoint_layout.addWidget(self.checkpoint_label)
        
        self.clear_checkpoint_btn = QPushButton("Xóa Checkpoint")
        self.clear_checkpoint_btn.clicked.connect(self.clear_checkpoint)
        self.clear_checkpoint_btn.setEnabled(False)
        self.checkpoint_layout.addWidget(self.clear_checkpoint_btn)
        
        checkpoint_frame.setLayout(self.checkpoint_layout)
        main_layout.addWidget(checkpoint_frame)
        
        # Account list
        accounts_frame = QFrame()
        accounts_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        accounts_layout = QVBoxLayout()
        accounts_layout.addWidget(QLabel("<b>Tài khoản:</b>"))
        self.accounts_list = QListWidget()
        self.accounts_list.setAlternatingRowColors(True)
        self.accounts_list.setStyleSheet("""
            QListWidget {
                font-size: 12px;
                line-height: 1.4;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:alternate {
                background-color: #f8f8f8;
            }
        """)
        accounts_layout.addWidget(self.accounts_list)
        accounts_frame.setLayout(accounts_layout)
        main_layout.addWidget(accounts_frame)
        
        # Progress section
        progress_frame = QFrame()
        progress_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        progress_layout = QVBoxLayout()
        progress_layout.addWidget(QLabel("<b>Tiến trình:</b>"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                height: 20px;
                text-align: center;
                font-weight: bold;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setStyleSheet("color: #1a73e8; font-weight: bold;")
        progress_layout.addWidget(self.status_label)
        
        # Thêm label hiển thị mức tiêu thụ mạng
        self.network_usage_label = QLabel("Mức tiêu thụ mạng: 0.00 MB")
        self.network_usage_label.setStyleSheet("color: #388e3c; font-weight: bold;")
        progress_layout.addWidget(self.network_usage_label)
        
        progress_frame.setLayout(progress_layout)
        main_layout.addWidget(progress_frame)
        
        # Buttons
        button_frame = QFrame()
        button_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.start_btn = QPushButton("Bắt đầu")
        self.start_btn.clicked.connect(self.start_login_process)
        button_layout.addWidget(self.start_btn)
        
        self.resume_btn = QPushButton("Tiếp tục")
        self.resume_btn.clicked.connect(self.resume_login_process)
        self.resume_btn.setEnabled(False)
        button_layout.addWidget(self.resume_btn)
        
        self.stop_btn = QPushButton("Dừng")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.clicked.connect(self.stop_login_process)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        self.export_btn = QPushButton("Xuất kết quả")
        self.export_btn.setObjectName("exportButton")
        self.export_btn.clicked.connect(self.export_results)
        button_layout.addWidget(self.export_btn)
        
        button_frame.setLayout(button_layout)
        main_layout.addWidget(button_frame)
        
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
                    logger.info(f"Tải checkpoint: {data}")
                    return data
        except Exception as e:
            logger.error(f"Lỗi tải checkpoint: {str(e)}")
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
            logger.info(f"Lưu checkpoint: {data}")
            return True
        except Exception as e:
            logger.error(f"Lỗi lưu checkpoint: {str(e)}")
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
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/mail_example.csv")
        
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
            logger.info(log_msg)
            
            # Check if this file matches our checkpoint
            self.update_checkpoint_display()
            
        except Exception as e:
            error_msg = f"Failed to load CSV file: {str(e)}"
            QMessageBox.critical(self, "Error", error_msg)
            logger.error(error_msg, exc_info=True)
    
    def start_login_process(self):
        """Start the automated login process from the beginning"""
        if not self.accounts:
            msg = "Không có tài khoản nào được tải. Vui lòng tải file CSV trước."
            QMessageBox.warning(self, "No Accounts", msg)
            logger.warning(msg)
            return
            
        if self.login_thread and self.login_thread.isRunning():
            msg = "Quá trình đăng nhập đang chạy."
            QMessageBox.warning(self, "Process Running", msg)
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
            logger.warning(msg)
            return
            
        if self.login_thread and self.login_thread.isRunning():
            msg = "Quá trình đăng nhập đang chạy."
            QMessageBox.warning(self, "Process Running", msg)
            logger.warning(msg)
            return
        
        # Check if we have a valid checkpoint
        if not self.checkpoint_data["file"] or self.checkpoint_data["index"] <= 0:
            msg = "Không tìm thấy checkpoint để tiếp tục."
            QMessageBox.warning(self, "No Checkpoint", msg)
            logger.warning(msg)
            return
            
        # Check if the current file matches the checkpoint
        if self.current_csv_file != self.checkpoint_data["file"]:
            msg = f"File CSV hiện tại khác với file trong checkpoint. Vui lòng tải file {os.path.basename(self.checkpoint_data['file'])}."
            QMessageBox.warning(self, "File Mismatch", msg)
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
                    logger.info(f"Đã lưu checkpoint tại tài khoản #{current_index + 1}")
            
            self.login_thread.stop()
            self.status_label.setText("Stopping login process...")
            logger.info("Người dùng đã yêu cầu dừng quá trình đăng nhập")
    
    def add_log_message(self, message):
        """Add message to the log display"""
        logger.info(message)
    
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
        logger.info(f"Account {email}: {status} - {message}")
    
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
                logger.info(f"Đã xuất kết quả đăng nhập ra file: {file_path}")
            
            except Exception as e:
                error_msg = f"Failed to export results: {str(e)}"
                QMessageBox.critical(self, "Export Error", error_msg)
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
        logger.info(f"Proxy set to: {proxy if proxy else 'No proxy'}")
        
        # Show success message
        if proxy:
            QMessageBox.information(self, "Success", f"Proxy đã được set thành công: {proxy}")
        else:
            QMessageBox.information(self, "Success", "Đã tắt proxy")

    def handle_proxy_failed(self):
        """Handle proxy failure: pause and prompt user to enter a new proxy"""
        self.proxy_failed = True
        self.status_label.setText("Proxy failed. Please enter a new proxy and click Set Proxy, then Resume.")
        logger.warning("Proxy failed. Waiting for user to set a new proxy.")
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.resume_btn.setEnabled(True)
        self.set_proxy_btn.setEnabled(True)
        QMessageBox.warning(self, "Proxy Failed", "Proxy failed. Please enter a new proxy and click Set Proxy, then Resume.")


def main():
    # Thông báo khởi động ứng dụng
    logger.info("=== Khởi động Google Login Tool ===")
    
    # Khởi tạo monitor mạng
    monitor = NetworkUsageMonitor()
    monitor.start()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for a consistent look across platforms
    window = GoogleLoginTool()
    window.show()
    
    # Xử lý khi thoát ứng dụng
    exit_code = app.exec_()

    # Đo mức tiêu thụ mạng
    monitor.stop()
    mb_used = monitor.get_usage_mb()
    msg = f"Tổng dung lượng mạng đã sử dụng: {mb_used:.2f} MB"
    print(msg)
    logger.info(msg)
    # Hiển thị lên giao diện nếu có
    if hasattr(window, 'network_usage_label') and window.network_usage_label:
        window.network_usage_label.setText(f"Mức tiêu thụ mạng: {mb_used:.2f} MB")
    logger.info("=== Kết thúc Google Login Tool ===")
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.critical(f"Lỗi nghiêm trọng: {str(e)}", exc_info=True)
        raise
