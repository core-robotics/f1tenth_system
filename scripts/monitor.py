#!/usr/bin/env python3
import time, psutil, shutil, subprocess, threading

POLL = 0.5
ALPHA = 0.3
BAR_W = shutil.get_terminal_size((60, 20)).columns // 4

FULL  = "▓"
EMPTY = " "

def ewma(prev, x, a=ALPHA): 
    return x if prev is None else a*x + (1-a)*prev

def bar(pct, width=BAR_W, label=""):
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
            if "GR3D" not in line: continue
            for tok in line.split():
                if tok.endswith("%") and tok[:-1].isdigit():
                    holder["util"] = float(tok[:-1])
                    break
    threading.Thread(target=reader, daemon=True).start()
    return proc, holder

if __name__ == "__main__":
    psutil.cpu_percent(None)  # warmup
    proc, gpu = start_tegrastats()
    cpu_s = ram_s = gpu_s = None
    try:
        while True:
            cpu = psutil.cpu_percent(None)
            ram = psutil.virtual_memory().percent
            graw = gpu["util"]

            cpu_s = ewma(cpu_s, cpu)
            ram_s = ewma(ram_s, ram)
            gpu_s = ewma(gpu_s, graw) if graw is not None else None

            line = " | ".join([
                bar(cpu_s, label="CPU"),
                bar(ram_s, label="RAM"),
                bar(graw, label="GPU")
            ])
            print(line, end="\r", flush=True)
            time.sleep(POLL)
    except KeyboardInterrupt:
        print("\nExit")
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
