import ipaddress
import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor

from dify_plugin.entities import I18nObject, ParameterOption

logger = logging.getLogger(__name__)

_CACHE = {}
_TTL = 30
_MAX_HOSTS = 1024


def _probe(ip, port=9100, timeout=0.3):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return ip if s.connect_ex((ip, port)) == 0 else None


def _hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return ""


def _option(ip, note):
    label = f"{ip}（{note}）" if note else ip
    return ParameterOption(value=ip, label=I18nObject(en_US=label, zh_Hans=label))


def discover_printers(subnet, manual_ips=""):
    """扫描子网内开放9100端口的主机作为打印机候选，30秒缓存"""
    key = (subnet, manual_ips)
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]

    found = []
    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        logger.warning(f"扫描子网格式无效: {subnet}")
        net = None
    if net is not None and net.version == 4 and net.num_addresses <= _MAX_HOSTS:
        hosts = [str(h) for h in net.hosts()]
        with ThreadPoolExecutor(max_workers=128) as ex:
            found = [ip for ip in ex.map(_probe, hosts) if ip]
        logger.info(f"子网{subnet}扫描完成，发现{len(found)}台开放9100端口的主机")

    options, seen = [], set()
    if found:
        ex = ThreadPoolExecutor(max_workers=8)
        futures = {ip: ex.submit(_hostname, ip) for ip in found}
        for ip in sorted(found, key=ipaddress.ip_address):
            try:
                name = futures[ip].result(timeout=1.0)
            except Exception:
                name = ""
            options.append(_option(ip, name or "9100端口开放"))
            seen.add(ip)
        # 不等待挂起的DNS线程，避免拖慢下拉加载
        ex.shutdown(wait=False, cancel_futures=True)

    for raw in manual_ips.replace("，", ",").split(","):
        ip = raw.strip()
        if not ip or ip in seen:
            continue
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            continue
        options.append(_option(ip, "手动添加"))
        seen.add(ip)

    _CACHE[key] = (now, options)
    return options


def fetch_ip_options(credentials, parameter):
    if parameter != "printer_ip":
        return []
    creds = credentials or {}
    return discover_printers(
        creds.get("scan_subnet") or "192.168.1.0/24",
        creds.get("manual_ips") or "",
    )