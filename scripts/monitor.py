#!/usr/bin/env python3
import sys, time, psutil, shutil, subprocess, threading

POLL  = 0.5
ALPHA = 0.3
FULL  = "▓"     # 얇은 세로 블록 (원하면 "▓" 등으로 변경)
EMPTY = " "

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
    if pct is None:
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

if __name__ == "__main__":
    psutil.cpu_percent(None)  # warmup
    proc, gpu = start_tegrastats()

    cpu_s = ram_s = gpu_s = None
    first_paint = True
    try:
        hide_cursor()
        while True:
            w = bar_width()

            cpu = psutil.cpu_percent(None)
            ram = psutil.virtual_memory().percent
            graw = gpu["util"]

            cpu_s = ewma(cpu_s, cpu)
            ram_s = ewma(ram_s, ram)
            gpu_s = ewma(gpu_s, graw) if graw is not None else None

            lines = [
                bar(cpu_s, w, "CPU"),
                bar(ram_s, w, "RAM"),
                bar(graw,  w, "GPU"),
            ]

            if not first_paint:
                # 커서를 3줄 위로 올려서 같은 위치를 덮어씀
                cursor_up(len(lines))

            # 각 줄을 지우고 다시 출력
            for ln in lines:
                clear_line()
                sys.stdout.write(ln + "\n")
            sys.stdout.flush()

            first_paint = False
            time.sleep(POLL)

    except KeyboardInterrupt:
        pass
    finally:
        show_cursor()
        if proc and proc.poll() is None:
            proc.terminate()
        print("Exit")
