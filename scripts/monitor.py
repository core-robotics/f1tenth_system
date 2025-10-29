#!/usr/bin/env python3
import sys, time, psutil, shutil, subprocess, threading, math

# ===== ROS 2 =====
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import Float32

POLL  = 0.5
ALPHA = 0.3
FULL  = "▓"     # 얇은 세로 블록 (원하면 "▓" 등으로 변경)
EMPTY = " "

CPU_TOPIC = "/sys/cpu/percent"
RAM_TOPIC = "/sys/ram/percent"
GPU_TOPIC = "/sys/gpu/percent"

def term_width(default=60):
    try:
        return shutil.get_terminal_size((default, 20)).columns
    except Exception:
        return default

def bar_width():
    # CPU/RAM/GPU 세 줄 표시 + 라벨/공백 고려해 대략 1/3 폭 사용
    return max(10, term_width() // 3)

def ewma(prev, x, a=ALPHA):
    return x if prev is None else a*x + (1-a)*prev

def bar(pct, width, label=""):
    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        return f"{label}: {EMPTY*width} N/A"
    n = int(width * pct / 100)
    return f"{label}: {FULL*n}{EMPTY*(width-n)} {pct:5.1f}%"

def start_tegrastats(interval_ms=int(POLL*1000)):
    holder = {"util": None}
    try:
        proc = subprocess.Popen(
            ["tegrastats", "--interval", str(interval_ms)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1
        )
    except FileNotFoundError:
        return None, holder

    def reader():
        for line in proc.stdout:
            if "GR3D" not in line:
                continue
            # "GR3D_FREQ 47%" 같은 토큰에서 숫자만 추출
            for tok in line.split():
                if tok.endswith("%") and tok[:-1].isdigit():
                    holder["util"] = float(tok[:-1])
                    break
    threading.Thread(target=reader, daemon=True).start()
    return proc, holder

ESC = "\x1b"
def hide_cursor(): sys.stdout.write(f"{ESC}[?25l")
def show_cursor(): sys.stdout.write(f"{ESC}[?25h")
def clear_line():  sys.stdout.write(f"{ESC}[2K")
def cursor_up(n):  sys.stdout.write(f"{ESC}[{n}A")

class SysUsageNode(Node):
    def __init__(self):
        super().__init__("sys_usage_publisher")
        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST)

        self.pub_cpu = self.create_publisher(Float32, CPU_TOPIC, qos)
        self.pub_ram = self.create_publisher(Float32, RAM_TOPIC, qos)
        self.pub_gpu = self.create_publisher(Float32, GPU_TOPIC, qos)

        self.get_logger().info(
            f"Publishing usage (%) -> CPU:{CPU_TOPIC}, RAM:{RAM_TOPIC}, GPU:{GPU_TOPIC}"
        )

    def publish_values(self, cpu_pct: float, ram_pct: float, gpu_pct_or_nan: float):
        # 입력은 퍼센트 값(0~100). NaN 허용(특히 GPU 미가용 시).
        msg_cpu = Float32(); msg_cpu.data = float(cpu_pct)
        msg_ram = Float32(); msg_ram.data = float(ram_pct)
        msg_gpu = Float32(); msg_gpu.data = float(gpu_pct_or_nan)

        self.pub_cpu.publish(msg_cpu)
        self.pub_ram.publish(msg_ram)
        self.pub_gpu.publish(msg_gpu)

def main():
    psutil.cpu_percent(None)  # warmup psutil
    proc, gpu = start_tegrastats()

    # --- ROS 2 초기화 ---
    rclpy.init(args=None)
    node = SysUsageNode()

    cpu_s = ram_s = gpu_s = None
    first_paint = True
    try:
        hide_cursor()
        while rclpy.ok():
            w = bar_width()

            cpu = psutil.cpu_percent(None)
            ram = psutil.virtual_memory().percent
            graw = gpu["util"]

            cpu_s = ewma(cpu_s, cpu)
            ram_s = ewma(ram_s, ram)
            # GPU는 tegrastats 결과를 그대로 사용(스무딩은 UI 내부에서만 사용)
            gpu_display = graw if graw is not None else float("nan")

            # 터미널 UI
            lines = [
                bar(cpu_s, w, "CPU"),
                bar(ram_s, w, "RAM"),
                bar(gpu_display,  w, "GPU"),
            ]

            if not first_paint:
                cursor_up(len(lines))

            for ln in lines:
                clear_line()
                sys.stdout.write(ln + "\n")
            sys.stdout.flush()
            first_paint = False

            # ROS 2 퍼블리시 (CPU/RAM은 EWMA, GPU는 원시/NaN)
            node.publish_values(cpu_s, ram_s, gpu_display)

            # 콜백 처리(타이머/서비스는 없지만 ROS 신호 처리용)
            rclpy.spin_once(node, timeout_sec=0.0)

            time.sleep(POLL)

    except KeyboardInterrupt:
        pass
    finally:
        show_cursor()
        if proc and proc.poll() is None:
            proc.terminate()
        node.get_logger().info("Shutting down...")
        node.destroy_node()
        rclpy.shutdown()
        print("Exit")

if __name__ == "__main__":
    main()
