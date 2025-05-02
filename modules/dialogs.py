from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox

class CaptchaDialog(QDialog):
    """Dialog thông báo người dùng giải CAPTCHA thủ công"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Google CAPTCHA Detected")
        self.setModal(True)
        layout = QVBoxLayout()
        label = QLabel("Google đã yêu cầu xác minh CAPTCHA.<br>"
                       "Vui lòng giải CAPTCHA thủ công trên trình duyệt.<br>"
                       "Sau khi hoàn thành, nhấn 'Tiếp tục' để tiếp tục quá trình đăng nhập.")
        label.setWordWrap(True)
        layout.addWidget(label)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        self.setLayout(layout)
