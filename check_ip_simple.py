#!/usr/bin/env python3
"""
Script sederhana untuk mengecek IP address lokal dan public
"""

import socket
import requests


def check_ip():
    """Fungsi sederhana untuk cek IP lokal dan public"""
    
    # Local IP
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"Local IP: {local_ip}")
    except Exception as e:
        print(f"Error local IP: {e}")
    
    # Public IP
    try:
        public_ip = requests.get('https://api.ipify.org').text
        print(f"Public IP: {public_ip}")
    except Exception as e:
        print(f"Error public IP: {e}")


if __name__ == "__main__":
    check_ip()
