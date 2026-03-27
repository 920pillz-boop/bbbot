#!/usr/bin/env python3
"""
run_with_vless.py
─────────────────
Запускает Xray с VLESS-конфигом как локальный SOCKS5-прокси,
затем запускает Telegram-бота через этот прокси.

Использование:
    python run_with_vless.py "vless://UUID@HOST:PORT?security=tls&...#name"

Или через переменную окружения в .env:
    VLESS_LINK=vless://...
    python run_with_vless.py
"""

import asyncio
import io
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

# ── Принудительный UTF-8 для Windows-консоли ─────────────────────────────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Пытаемся загрузить .env ──────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SOCKS_PORT = int(os.getenv("VLESS_SOCKS_PORT", "10808"))
XRAY_BIN   = os.getenv("XRAY_BIN", "xray")          # путь к бинарнику xray
XRAY_CFG   = os.getenv("XRAY_CFG", "xray_config.json")


# ── Парсер VLESS-ссылки ───────────────────────────────────────────────────────

def parse_vless(link: str) -> dict:
    """
    Разбирает ссылку вида:
      vless://UUID@host:port?security=tls&sni=example.com&type=tcp&...#Remark

    Возвращает dict с полями:
      uuid, address, port, security, network, sni, path, host,
      headerType, flow, fp, pbk, sid, spx, remark
    """
    link = link.strip()
    if not link.startswith("vless://"):
        raise ValueError("Ссылка должна начинаться с vless://")

    # Убираем схему
    rest = link[len("vless://"):]

    # Remark — после #
    remark = ""
    if "#" in rest:
        rest, remark = rest.rsplit("#", 1)
        remark = urllib.parse.unquote(remark)

    # Params — после ?
    params_str = ""
    if "?" in rest:
        rest, params_str = rest.split("?", 1)
    params = dict(urllib.parse.parse_qsl(params_str))

    # UUID@host:port
    if "@" not in rest:
        raise ValueError("Нет символа @ в ссылке")
    uuid, hostport = rest.split("@", 1)

    # IPv6 вида [::1]:443
    if hostport.startswith("["):
        m = re.match(r"\[(.+?)\]:(\d+)", hostport)
        if not m:
            raise ValueError(f"Не удалось распарсить IPv6: {hostport}")
        address = m.group(1)
        port = int(m.group(2))
    else:
        parts = hostport.rsplit(":", 1)
        address = parts[0]
        port = int(parts[1]) if len(parts) == 2 else 443

    return {
        "uuid":       uuid,
        "address":    address,
        "port":       port,
        "security":   params.get("security", "none"),
        "network":    params.get("type", "tcp"),
        "sni":        params.get("sni", address),
        "path":       urllib.parse.unquote(params.get("path", "/")),
        "host":       params.get("host", address),
        "headerType": params.get("headerType", "none"),
        "flow":       params.get("flow", ""),
        "fp":         params.get("fp", ""),
        "pbk":        params.get("pbk", ""),
        "sid":        params.get("sid", ""),
        "spx":        urllib.parse.unquote(params.get("spx", "")),
        "remark":     remark,
    }


# ── Генератор xray config.json ────────────────────────────────────────────────

def build_xray_config(v: dict, socks_port: int) -> dict:
    """Строит минимальный xray config.json для VLESS-аутбаунда."""

    # ── Transport settings ──
    network = v["network"]  # tcp / ws / grpc / h2 / quic / httpupgrade

    stream_settings: dict = {"network": network}

    if network == "ws":
        stream_settings["wsSettings"] = {
            "path": v["path"],
            "headers": {"Host": v["host"]} if v["host"] else {}
        }
    elif network == "grpc":
        stream_settings["grpcSettings"] = {
            "serviceName": v["path"].lstrip("/")
        }
    elif network == "h2":
        stream_settings["httpSettings"] = {
            "host": [v["host"]] if v["host"] else [],
            "path": v["path"]
        }
    elif network == "httpupgrade":
        stream_settings["httpupgradeSettings"] = {
            "path": v["path"],
            "host": v["host"]
        }
    elif network == "tcp":
        if v["headerType"] == "http":
            stream_settings["tcpSettings"] = {
                "header": {
                    "type": "http",
                    "request": {
                        "path": [v["path"]],
                        "headers": {"Host": [v["host"]]}
                    }
                }
            }

    # ── TLS / Reality ──
    security = v["security"]
    if security == "tls":
        tls_cfg: dict = {
            "serverName": v["sni"],
            "allowInsecure": False
        }
        if v["fp"]:
            tls_cfg["fingerprint"] = v["fp"]
        if v["spx"]:
            tls_cfg["spiderX"] = v["spx"]
        stream_settings["tlsSettings"] = tls_cfg
        stream_settings["security"] = "tls"

    elif security == "reality":
        reality_cfg: dict = {
            "serverName": v["sni"],
            "fingerprint": v["fp"] or "chrome",
            "show": False,
        }
        if v["pbk"]:
            reality_cfg["publicKey"] = v["pbk"]
        if v["sid"]:
            reality_cfg["shortId"] = v["sid"]
        if v["spx"]:
            reality_cfg["spiderX"] = v["spx"]
        stream_settings["realitySettings"] = reality_cfg
        stream_settings["security"] = "reality"

    else:
        stream_settings["security"] = "none"

    # ── Outbound ──
    vless_user: dict = {"id": v["uuid"], "encryption": "none"}
    if v["flow"]:
        vless_user["flow"] = v["flow"]

    outbound = {
        "protocol": "vless",
        "settings": {
            "vnext": [{
                "address": v["address"],
                "port": v["port"],
                "users": [vless_user]
            }]
        },
        "streamSettings": stream_settings,
        "tag": "vless-out"
    }

    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "listen": "127.0.0.1",
            "port": socks_port,
            "protocol": "socks",
            "settings": {
                "auth": "noauth",
                "udp": True
            },
            "tag": "socks-in"
        }],
        "outbounds": [
            outbound,
            {"protocol": "freedom", "tag": "direct"}
        ],
        "routing": {
            "rules": [{
                "type": "field",
                "inboundTag": ["socks-in"],
                "outboundTag": "vless-out"
            }]
        }
    }
    return config


# ── Проверка доступности xray ─────────────────────────────────────────────────

def find_xray() -> str | None:
    """Ищет xray в PATH и рядом со скриптом."""
    import shutil
    found = shutil.which(XRAY_BIN)
    if found:
        return found
    # Рядом со скриптом
    local = Path(__file__).parent / XRAY_BIN
    if local.exists():
        return str(local)
    local_exe = Path(__file__).parent / (XRAY_BIN + ".exe")
    if local_exe.exists():
        return str(local_exe)
    return None


# ── Основной запуск ───────────────────────────────────────────────────────────

def run():
    # 1. Получаем VLESS-ссылку
    vless_link = None
    if len(sys.argv) > 1:
        vless_link = sys.argv[1]
    else:
        vless_link = os.getenv("VLESS_LINK", "").strip()

    if not vless_link:
        print("❌ VLESS-ссылка не передана.\n")
        print("Передайте её как аргумент:")
        print('  python run_with_vless.py "vless://UUID@host:443?security=tls&...#name"\n')
        print("Или добавьте в .env файл:")
        print('  VLESS_LINK=vless://...')
        sys.exit(1)

    # 2. Парсим ссылку
    try:
        v = parse_vless(vless_link)
    except ValueError as e:
        print(f"❌ Ошибка разбора VLESS-ссылки: {e}")
        sys.exit(1)

    print(f"✅ VLESS разобран: {v['remark'] or v['address']}:{v['port']}")
    print(f"   UUID:     {v['uuid'][:8]}...")
    print(f"   Security: {v['security']}")
    print(f"   Network:  {v['network']}")

    # 3. Ищем xray
    xray_bin = find_xray()
    if not xray_bin:
        print("\n❌ Xray не найден!")
        print_xray_install_guide()
        sys.exit(1)

    print(f"\n✅ Xray найден: {xray_bin}")

    # 4. Пишем xray config
    cfg = build_xray_config(v, SOCKS_PORT)
    cfg_path = Path(XRAY_CFG)
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    print(f"✅ Xray config записан: {cfg_path}")

    # 5. Запускаем xray
    print(f"\n🚀 Запускаю Xray (SOCKS5 на 127.0.0.1:{SOCKS_PORT})...")
    xray_proc = subprocess.Popen(
        [xray_bin, "run", "-c", str(cfg_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Ждём старта (ищем признак готовности в логах)
    ready = False
    timeout = 10
    start = time.time()
    while time.time() - start < timeout:
        line = xray_proc.stdout.readline()
        if line:
            print(f"  [xray] {line.rstrip()}")
        if xray_proc.poll() is not None:
            print("❌ Xray завершился неожиданно!")
            sys.exit(1)
        # Xray пишет "Xray x.x.x started" когда готов
        if "started" in line.lower() or "listening" in line.lower():
            ready = True
            break
        time.sleep(0.1)

    if not ready:
        print(f"⚠️  Xray не подтвердил готовность за {timeout}с, но продолжаем...")
    else:
        print(f"✅ Xray готов, SOCKS5 слушает на 127.0.0.1:{SOCKS_PORT}")

    # 6. Выставляем прокси для aiogram через переменные окружения
    proxy_url = f"socks5://127.0.0.1:{SOCKS_PORT}"
    os.environ["TELEGRAM_PROXY"] = proxy_url
    # aiohttp понимает эту переменную
    os.environ["ALL_PROXY"]   = proxy_url
    os.environ["all_proxy"]   = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    os.environ["https_proxy"] = proxy_url

    print(f"\n✅ Прокси установлен: {proxy_url}")
    print("🤖 Запускаю бота...\n" + "─" * 50)

    # 7. Запускаем бота в том же процессе
    try:
        import bot as bot_module
        asyncio.run(bot_module.main())
    except KeyboardInterrupt:
        print("\n⛔ Остановлено пользователем.")
    finally:
        print("🛑 Останавливаю Xray...")
        xray_proc.terminate()
        try:
            xray_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            xray_proc.kill()
        print("✅ Xray остановлен.")


def print_xray_install_guide():
    print("""
╔══════════════════════════════════════════════════════╗
║           Как установить Xray                        ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Linux / macOS:                                      ║
║    bash <(curl -L https://github.com/XTLS/Xray-core  ║
║      /releases/latest/download/install-release.sh)   ║
║                                                      ║
║  Или скачайте вручную:                               ║
║    https://github.com/XTLS/Xray-core/releases        ║
║    → Xray-linux-64.zip / Xray-windows-64.zip         ║
║    → Распакуйте xray (или xray.exe) рядом с ботом    ║
║                                                      ║
║  Windows (winget):                                   ║
║    winget install XTLS.Xray                          ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    run()
