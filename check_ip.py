#!/usr/bin/env python3
"""
Script untuk mengecek IP address lokal dan public
"""

import socket
import requests
from urllib.request import urlopen
import json


def get_local_ip():
    """
    Mendapatkan IP address lokal (private)
    """
    try:
        # Cara 1: Menggunakan socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return local_ip
    except Exception as e:
        print(f"Error mendapatkan local IP: {e}")
        return None


def get_local_ip_alternative():
    """
    Alternatif untuk mendapatkan IP address lokal
    """
    try:
        # Koneksi ke server eksternal (tidak benar-benar mengirim data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        print(f"Error mendapatkan local IP (alternatif): {e}")
        return None


def get_public_ip_method1():
    """
    Mendapatkan public IP address - Method 1 (requests)
    """
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        public_ip = response.json()['ip']
        return public_ip
    except Exception as e:
        print(f"Error method 1: {e}")
        return None


def get_public_ip_method2():
    """
    Mendapatkan public IP address - Method 2 (urllib)
    """
    try:
        response = urlopen('https://api.ipify.org?format=json', timeout=5)
        data = json.loads(response.read().decode('utf-8'))
        public_ip = data['ip']
        return public_ip
    except Exception as e:
        print(f"Error method 2: {e}")
        return None


def get_public_ip_method3():
    """
    Mendapatkan public IP address - Method 3 (alternative API)
    """
    try:
        response = requests.get('https://checkip.amazonaws.com', timeout=5)
        public_ip = response.text.strip()
        return public_ip
    except Exception as e:
        print(f"Error method 3: {e}")
        return None


def get_detailed_network_info():
    """
    Mendapatkan informasi network yang lebih lengkap
    """
    try:
        response = requests.get('https://ipapi.co/json/', timeout=5)
        network_info = response.json()
        return network_info
    except Exception as e:
        print(f"Error mendapatkan detailed network info: {e}")
        return None


def main():
    print("=" * 60)
    print("IP ADDRESS CHECKER")
    print("=" * 60)
    
    # Local IP
    print("\n[LOCAL IP ADDRESS]")
    local_ip = get_local_ip()
    if local_ip:
        print(f"✓ Local IP: {local_ip}")
    else:
        print("✗ Tidak berhasil mendapatkan Local IP")
        local_ip_alt = get_local_ip_alternative()
        if local_ip_alt:
            print(f"✓ Local IP (Alternative): {local_ip_alt}")
    
    # Public IP
    print("\n[PUBLIC IP ADDRESS]")
    public_ip = get_public_ip_method1()
    if public_ip:
        print(f"✓ Public IP: {public_ip}")
    else:
        print("✗ Method 1 gagal, mencoba method 2...")
        public_ip = get_public_ip_method2()
        if public_ip:
            print(f"✓ Public IP (Method 2): {public_ip}")
        else:
            print("✗ Method 2 gagal, mencoba method 3...")
            public_ip = get_public_ip_method3()
            if public_ip:
                print(f"✓ Public IP (Method 3): {public_ip}")
            else:
                print("✗ Semua method gagal!")
    
    # Detailed Network Information
    print("\n[DETAILED NETWORK INFORMATION]")
    network_info = get_detailed_network_info()
    if network_info:
        print(f"✓ Public IP: {network_info.get('ip')}")
        print(f"✓ Hostname: {network_info.get('hostname')}")
        print(f"✓ City: {network_info.get('city')}")
        print(f"✓ Region: {network_info.get('region')}")
        print(f"✓ Country: {network_info.get('country_name')}")
        print(f"✓ Timezone: {network_info.get('timezone')}")
        print(f"✓ ISP: {network_info.get('org')}")
    else:
        print("✗ Tidak berhasil mendapatkan detailed network info")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
