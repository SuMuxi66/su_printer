import urllib.parse
import socket
import ipaddress

def is_safe_url(url):
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Resolve hostname to IP
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        
        # Check if IP is private, loopback, etc.
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_multicast:
            return False
        return True
    except Exception as e:
        print(e)
        return False

print("localhost:", is_safe_url("http://localhost"))
print("127.0.0.1:", is_safe_url("http://127.0.0.1"))
print("192.168.1.1:", is_safe_url("http://192.168.1.1"))
print("example.com:", is_safe_url("http://example.com"))
