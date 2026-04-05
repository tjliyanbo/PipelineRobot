import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import os
import threading

class SimulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("管道机器人模拟器 - 控制台")
        
        # Center the window
        window_width = 360
        window_height = 200
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x_cordinate = int((screen_width/2) - (window_width/2))
        y_cordinate = int((screen_height/2) - (window_height/2))
        self.root.geometry(f"{window_width}x{window_height}+{x_cordinate}+{y_cordinate}")
        self.root.resizable(False, False)
        
        self.process = None
        self.setup_ui()

    def setup_ui(self):
        style = ttk.Style()
        # Use 'clam' theme for a cleaner modern look if available
        if 'clam' in style.theme_names():
            style.theme_use('clam')
            
        style.configure("TButton", font=("Microsoft YaHei", 10), padding=6)
        style.configure("Status.TLabel", font=("Microsoft YaHei", 12, "bold"))
        style.configure("Title.TLabel", font=("Microsoft YaHei", 14, "bold"))
        
        main_frame = ttk.Frame(self.root, padding="20 20 20 20")
        main_frame.pack(expand=True, fill='both')
        
        ttk.Label(main_frame, text="🤖 管道机器人 3D 模拟器", style="Title.TLabel").pack(pady=(0, 15))
        
        self.status_var = tk.StringVar()
        self.status_var.set("● 状态: 已停止")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, style="Status.TLabel", foreground="#e74c3c")
        self.status_label.pack(pady=(0, 20))
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack()
        
        self.btn_start = ttk.Button(btn_frame, text="▶ 启动模拟器", command=self.start_sim)
        self.btn_start.grid(row=0, column=0, padx=10)
        
        self.btn_stop = ttk.Button(btn_frame, text="⏹ 关闭模拟器", command=self.stop_sim, state=tk.DISABLED)
        self.btn_stop.grid(row=0, column=1, padx=10)

    def start_sim(self):
        if self.process is None or self.process.poll() is not None:
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulator.py")
            try:
                # 启动子进程，不显示控制台黑窗（Windows 特定配置）
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE

                self.process = subprocess.Popen(
                    [sys.executable, script_path],
                    startupinfo=startupinfo,
                    cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
                )
                
                self.btn_start.config(state=tk.DISABLED)
                self.btn_stop.config(state=tk.NORMAL)
                self.status_var.set("● 状态: 运行中")
                self.status_label.config(foreground="#2ecc71")
                
                # 监控进程是否意外退出
                threading.Thread(target=self.monitor_process, daemon=True).start()
            except Exception as e:
                messagebox.showerror("启动失败", f"无法启动模拟器程序:\n{str(e)}")

    def stop_sim(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()
            self.process = None
            
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_var.set("● 状态: 已停止")
        self.status_label.config(foreground="#e74c3c")

    def monitor_process(self):
        if self.process:
            self.process.wait()
            # 必须使用 after() 将 UI 更新调度回主线程
            self.root.after(0, self.on_process_ended)
            
    def on_process_ended(self):
        # 只有在它意外退出或被外部关闭时才更新UI（避免跟 stop_sim 冲突）
        if self.process is not None:
            self.process = None
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            self.status_var.set("● 状态: 已停止")
            self.status_label.config(foreground="#e74c3c")

    def on_closing(self):
        self.stop_sim()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SimulatorGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
