"""
Celery Worker / Beat 启动脚本

用法:
    # 启动 Worker（所有队列）
    python scripts/start_worker.py worker

    # 启动 Worker（指定队列）
    python scripts/start_worker.py worker --queues default,high_priority

    # 启动 Beat 调度器
    python scripts/start_worker.py beat

    # 启动 Worker + Beat（开发模式）
    python scripts/start_worker.py dev
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# 确保 backend 目录在 Python path 中
BACKEND_DIR = str(Path(__file__).parent.parent)
os.environ.setdefault("PYTHONPATH", BACKEND_DIR)

CELERY_APP = "app.celery_app:celery_app"

# 所有队列（与 celery_app.py 中定义的保持一致）
ALL_QUEUES = "default,high_priority,ai_gateway,scheduled,notification"


def start_worker(queues: str | None = None, concurrency: int | None = None, loglevel: str = "info") -> None:
    cmd = [
        sys.executable, "-m", "celery",
        "-A", CELERY_APP,
        "worker",
        f"--loglevel={loglevel}",
    ]
    if queues:
        cmd.extend(["-Q", queues])
    if concurrency:
        cmd.extend(["-c", str(concurrency)])
    subprocess.run(cmd, check=True)


def start_beat(loglevel: str = "info") -> None:
    cmd = [
        sys.executable, "-m", "celery",
        "-A", CELERY_APP,
        "beat",
        f"--loglevel={loglevel}",
    ]
    subprocess.run(cmd, check=True)


def start_dev(loglevel: str = "info") -> None:
    import platform
    if platform.system() == "Windows":
        # Windows 不支持 --beat，需要分开启动 worker 和 beat
        import threading
        
        def run_worker():
            subprocess.run([
                sys.executable, "-m", "celery",
                "-A", CELERY_APP,
                "worker",
                "-Q", ALL_QUEUES,
                f"--loglevel={loglevel}",
                "--pool=solo",
            ], cwd=BACKEND_DIR)
        
        def run_beat():
            subprocess.run([
                sys.executable, "-m", "celery",
                "-A", CELERY_APP,
                "beat",
                f"--loglevel={loglevel}",
            ], cwd=BACKEND_DIR)
        
        print(f"Starting Celery Worker + Beat (Windows mode, cwd={BACKEND_DIR})")
        worker_thread = threading.Thread(target=run_worker, daemon=True)
        beat_thread = threading.Thread(target=run_beat, daemon=True)
        worker_thread.start()
        beat_thread.start()
        
        try:
            worker_thread.join()
        except KeyboardInterrupt:
            print("\nStopping...")
    else:
        cmd = [
            sys.executable, "-m", "celery",
            "-A", CELERY_APP,
            "worker",
            "--beat",
            "-Q", ALL_QUEUES,
            f"--loglevel={loglevel}",
            "-c", "2",
        ]
        subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Celery Worker/Beat launcher")
    parser.add_argument("mode", choices=["worker", "beat", "dev"])
    parser.add_argument("--queues", "-Q", type=str, default=None)
    parser.add_argument("--concurrency", "-c", type=int, default=None)
    parser.add_argument("--loglevel", "-l", type=str, default="info")
    args = parser.parse_args()

    if args.mode == "worker":
        start_worker(args.queues, args.concurrency, args.loglevel)
    elif args.mode == "beat":
        start_beat(args.loglevel)
    elif args.mode == "dev":
        start_dev(args.loglevel)


if __name__ == "__main__":
    main()
