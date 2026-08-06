# File: auth.py
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import platform
import os
import sys
import threading
import time
import hashlib

WORKER_URL = "https://jolly-wave-59b9.cuongvunhat755.workers.dev/" 
# Resolve LICENSE_FILE dynamically based on execution mode
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

LICENSE_FILE = os.path.join(ROOT_DIR, "license.key")
PRODUCT_FILE = os.path.join(ROOT_DIR, "product.key")

CLIENT_SECRET_SALT = "DkcTool_S3cr3t_S4lt_2026!@#"

# >>> DÁN PUBLIC KEY (TỪ BƯỚC 1) VÀO GIỮA 3 DẤU NGOẶC KÉP DƯỚI ĐÂY <<<
RSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyFKks96pTE/5vhmrzttq
XL8867VLWTI+MzVWDqrtD/DWYoYNJ52dvz0nzjbDPdgKeB8BrKrMUCbOZYXkmonO
4a4k3c0/rUe0kADGSbMj8bOjgs5A9YFOcwfeuDBQICJN2rWf7umeVZ6UkhBAl3oZ
toKtYi9RVbr9CL36j6uDTejKY9Q+F0IDOuuSuJ0jdXk0G6txNxmYi6+FmMCHvN6n
lY0BBazG4/JzPkfgEAlD+9LJAbvEynSG48SZ6YCDC2W1ygGd3WFm3xkPXTvSnltq
BRqcm1PZqtSxCrmRycF1GEKbAJqn/N3+mW5ou7m506PGBvfza337qV0osfETDC2v
GwIDAQAB
-----END PUBLIC KEY-----"""

def get_hwid():
    try:
        if platform.system() == "Windows":
            return subprocess.check_output('wmic csproduct get uuid', creationflags=subprocess.CREATE_NO_WINDOW).decode().split('\n')[1].strip()
        import uuid
        return str(uuid.getnode())
    except Exception:
        import uuid
        return str(uuid.getnode())

def generate_signature(key, hwid, timestamp):
    raw_str = f"{key}{hwid}{timestamp}{CLIENT_SECRET_SALT}"
    return hashlib.sha256(raw_str.encode()).hexdigest()
def get_product():
    # 1. Try to read from PyInstaller temp folder first (if bundled inside the EXE)
    if hasattr(sys, '_MEIPASS'):
        bundled_product_file = os.path.join(sys._MEIPASS, "product.key")
        if os.path.exists(bundled_product_file):
            try:
                with open(bundled_product_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except:
                pass
                
    # 2. Fallback to external product.key beside the EXE
    try:
        with open(PRODUCT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return ""

class AuthApp:
    def __init__(self, root, on_success_callback):
        self.root = root
        self.on_success = on_success_callback
        self.root.title("Xác Thực Bản Quyền DKCTool")
        self.root.geometry("450x240")
        self.root.resizable(False, False)
        self.root.eval('tk::PlaceWindow . center')
        self.root.configure(bg="#1a1a1a")
        
        # Load Window Icon
        if getattr(sys, 'frozen', False):
            logo_path = os.path.join(os.path.dirname(sys.executable), "logo.ico")
            if not os.path.exists(logo_path) and hasattr(sys, '_MEIPASS'):
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
        else:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            
        if os.path.exists(logo_path):
            try:
                self.root.iconbitmap(logo_path)
            except Exception:
                pass
        
        main_frame = tk.Frame(self.root, bg="#1a1a1a", padx=25, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.title_lbl = tk.Label(
            main_frame, 
            text="HỆ THỐNG XÁC THỰC BẢN QUYỀN", 
            font=("Segoe UI", 12, "bold"), 
            bg="#1a1a1a", 
            fg="#ffffff"
        )
        self.title_lbl.pack(pady=(0, 10))
        
        self.instruction_lbl = tk.Label(
            main_frame, 
            text="Vui lòng nhập License Key để tiếp tục:", 
            font=("Segoe UI", 10), 
            bg="#1a1a1a", 
            fg="#aaaaaa"
        )
        self.instruction_lbl.pack(anchor=tk.W, pady=(0, 5))
        
        self.key_var = tk.StringVar()
        self.key_entry = tk.Entry(
            main_frame, 
            textvariable=self.key_var, 
            font=("Segoe UI", 11), 
            bg="#252526", 
            fg="#ffffff", 
            insertbackground="#ffffff", 
            relief=tk.FLAT, 
            bd=0, 
            highlightbackground="#333333",
            highlightcolor="#0078d4",
            highlightthickness=1
        )
        self.key_entry.pack(fill=tk.X, ipady=6, pady=(0, 10))
        
        self.status_lbl = tk.Label(
            main_frame, 
            text="", 
            font=("Segoe UI", 9, "italic"), 
            bg="#1a1a1a", 
            fg="#0078d4"
        )
        self.status_lbl.pack(pady=(0, 10))
        
        self.btn_submit = tk.Button(
            main_frame,
            text="Kích Hoạt / Đăng Nhập",
            command=self.start_verify,
            font=("Segoe UI", 10, "bold"),
            bg="#0078d4",
            fg="#ffffff",
            activebackground="#0086f0",
            activeforeground="#ffffff",
            bd=0,
            cursor="hand2",
            padx=15,
            pady=6
        )
        self.btn_submit.pack()
        
        # Chỉ tạo thư mục nếu LICENSE_FILE có chứa đường dẫn thư mục
        dir_name = os.path.dirname(LICENSE_FILE)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
        self.root.after(100, self.check_offline_jwt)

    def check_offline_jwt(self):
        if not os.path.exists(LICENSE_FILE): return
        import jwt
        try:
            with open(LICENSE_FILE, "r") as f: token = f.read().strip()
            if not token: return
            
            self.status_lbl.config(text="Đang kiểm tra phiên làm việc cục bộ...", fg="#0078d4")
            
            # Giải mã bằng Public Key (RS256). Lỗi hoặc hết hạn tự động throw Exception
            payload = jwt.decode(token, RSA_PUBLIC_KEY, algorithms=["RS256"])
            
            if payload.get("hwid") != get_hwid():
                raise jwt.InvalidTokenError("Sai HWID.")
 
            self.status_lbl.config(text="Đăng nhập tự động thành công!", fg="#2ea44f")
            self.root.after(500, self.auth_success)
            
        except jwt.ExpiredSignatureError:
            self.status_lbl.config(text="Phiên đăng nhập hết hạn. Đang kết nối máy chủ...", fg="#e0a100")
            try:
                unverified_payload = jwt.decode(token, options={"verify_signature": False})
                self.key_var.set(unverified_payload.get("key", ""))
                self.start_verify()
            except: pass
        except Exception:
            self.status_lbl.config(text="Dữ liệu xác thực không hợp lệ. Vui lòng nhập lại.", fg="#ff3333")
            if os.path.exists(LICENSE_FILE): os.remove(LICENSE_FILE)

    def start_verify(self):
        key = self.key_var.get().strip()
        if not key:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập License Key!")
            return
            
        self.btn_submit.config(state=tk.DISABLED, text="Đang kết nối Server...", bg="#333333", fg="#888888")
        self.status_lbl.config(text="Đang lấy mã xác thực...", fg="#0078d4")
        self.key_entry.config(state=tk.DISABLED, bg="#1a1a1a", highlightbackground="#222222")
        
        threading.Thread(target=self.verify_logic, args=(key,), daemon=True).start()

    def verify_logic(self, key):
        import requests
        hwid = get_hwid()
        product = get_product()
        timestamp = str(int(time.time()))
        signature = generate_signature(key, hwid, timestamp)
        
        payload = {"key": key, "product": product, "hwid": hwid, "timestamp": timestamp, "signature": signature}
        
        try:
            resp = requests.post(WORKER_URL, json=payload, timeout=10)
            data = resp.json()
            
            if resp.status_code == 200 and data.get("success"):
                token = data.get("token")
                with open(LICENSE_FILE, "w") as f: f.write(token)
                self.root.after(0, self.auth_success)
            else:
                msg = data.get("message", "Lỗi xác thực không rõ nguyên nhân!")
                self.root.after(0, lambda: self.auth_failed(msg))
        except Exception as e:
            self.root.after(0, lambda: self.auth_failed("Lỗi mạng/kết nối."))

    def auth_success(self):
        self.root.destroy()
        self.on_success()

    def auth_failed(self, error_msg):
        self.btn_submit.config(state=tk.NORMAL, text="Kích Hoạt / Đăng Nhập", bg="#0078d4", fg="#ffffff")
        self.status_lbl.config(text=error_msg, fg="#ff3333")
        self.key_entry.config(state=tk.NORMAL, bg="#252526", highlightbackground="#333333")
        if os.path.exists(LICENSE_FILE):
            try: os.remove(LICENSE_FILE)
            except: pass
        messagebox.showerror("Lỗi Kích Hoạt", error_msg)

def run_authentication(on_success_callback):
    root = tk.Tk()
    app = AuthApp(root, on_success_callback)
    root.mainloop()