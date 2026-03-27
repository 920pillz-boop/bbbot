"""
start.py — Умный запуск: туннель + бот с автоперезапуском.
Запускай: python start.py
"""
import os
import subprocess
import sys
import time
import threading
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("starter")

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BOT_DIR, ".env")

bot_proc = None
stop_event = threading.Event()


def update_env(key: str, value: str):
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}\n")
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def kill_proc(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def run_bot(webapp_url: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["WEBAPP_URL"] = webapp_url
    proc = subprocess.Popen(
        [sys.executable, "bot.py"],
        cwd=BOT_DIR,
        env=env,
    )
    log.info(f"Bot started (pid={proc.pid}) url={webapp_url}")
    return proc


def start_tunnel_and_get_url() -> str | None:
    """Запускает localtunnel и возвращает URL (или None при ошибке)."""
    proc = subprocess.Popen(
        "npx --yes localtunnel --port 8080 --local-host 127.0.0.1",
        shell=True,
        cwd=BOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url = None
    deadline = time.time() + 30
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if "your url is:" in line:
            url = line.split("your url is:")[-1].strip()
            break
    return url, proc


def main():
    global bot_proc
    log.info("=== Own Agency Bot Starter ===")
    log.info("Нажми Ctrl+C для остановки")

    while not stop_event.is_set():
        log.info("Запускаю туннель...")
        url, tunnel_proc = start_tunnel_and_get_url()

        if not url:
            log.warning("Не удалось получить URL туннеля, retry через 5 сек...")
            kill_proc(tunnel_proc)
            time.sleep(5)
            continue

        log.info(f"Туннель: {url}")
        update_env("WEBAPP_URL", url)

        kill_proc(bot_proc)
        bot_proc = run_bot(url)

        # Ждём пока туннель или бот не упадут
        while not stop_event.is_set():
            if tunnel_proc.poll() is not None:
                log.warning("Туннель упал, перезапускаю...")
                break
            if bot_proc.poll() is not None:
                log.warning("Бот упал, перезапускаю...")
                kill_proc(tunnel_proc)
                break
            time.sleep(2)

        time.sleep(3)

    kill_proc(bot_proc)
    log.info("Остановлено.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Ctrl+C — останавливаюсь...")
        stop_event.set()
        kill_proc(bot_proc)
