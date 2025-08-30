import psutil
import os

class NetworkUsageMonitor:
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_bytes = None
        self.end_bytes = None

    def _get_bytes(self):
        # Lấy tổng số bytes gửi/nhận của process hiện tại
        io_counters = self.process.io_counters()
        # Một số hệ điều hành có thể không hỗ trợ network io_counters cho process, fallback về 0
        sent = getattr(io_counters, 'other', 0)
        recv = getattr(io_counters, 'read_bytes', 0)
        return sent + recv

    def start(self):
        self.start_bytes = self._get_bytes()

    def stop(self):
        self.end_bytes = self._get_bytes()

    def get_usage_mb(self):
        if self.start_bytes is not None and self.end_bytes is not None:
            used_bytes = self.end_bytes - self.start_bytes
            return used_bytes / (1024 * 1024)
        return 0.0
