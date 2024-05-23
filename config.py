import random
import shutil
import socket
import string
import threading
import requests
import base64
import re
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from v2tj import convert_uri_json


def find_free_port():
    while True:
        # Generate a random port number between 1024 and 65535
        port = random.randint(1024, 65535)

        # Check if the port is free
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                # If bind is successful, the port is free
                return port
            except OSError:
                # If bind raises an OSError, the port is already in use
                continue


def generate_v2ray_config(vless_link, inbound_port):
    if not vless_link.startswith('vless://'):
        raise ValueError("Unsupported V2Ray protocol")

    # Remove the scheme
    vless_link = vless_link[8:]

    # Split the link into userinfo and the rest
    userinfo, _, host_info = vless_link.partition('@')

    if not userinfo or not host_info:
        raise ValueError("Invalid VLESS link format")

    # Extract UUID from userinfo
    user_id = userinfo

    # Split host_info into host and query string
    if '?' in host_info:
        host, query_string = host_info.split('?', 1)
    else:
        host, query_string = host_info, ""

    # Extract address and port from host
    if ':' in host:
        address, port = host.split(':', 1)
        port = int(port.replace("/", ""))
    else:
        raise ValueError("Host must include a port number")

    query_string, tag = query_string.split('#')

    # Parse the query string into a dictionary
    query_params = dict(param.split('=') for param in query_string.split('&') if '=' in param)

    # Extract VLESS parameters
    flow = query_params.get('flow')
    encryption = query_params.get('encryption', 'none')
    network = query_params.get('type', 'tcp')
    security = query_params.get('security')
    sni = query_params.get('sni')
    alpn = query_params.get('alpn')
    host = query_params.get('host')
    path = query_params.get('path', '')

    headers = {"Host": host} if host else {}

    # Construct the V2Ray configuration
    v2ray_config = {
        "inbounds": [
            {
                "port": inbound_port,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {
                    "auth": "noauth",
                    "udp": False,
                    "ip": "127.0.0.1"
                }
            }
        ],
        "outbounds": [
            {
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": address,
                            "port": port,
                            "users": [
                                {
                                    "id": user_id,
                                    "encryption": encryption,
                                    "flow": flow
                                }
                            ]
                        }
                    ]
                },
                "streamSettings": {
                    "network": network,
                    "security": security,
                    "tlsSettings": {
                        "serverName": sni,
                        "alpn": alpn.split(',') if alpn else []
                    } if security == "tls" else {},
                    "wsSettings": {
                        "path": path,
                        "headers": headers
                    } if network == "ws" else {}
                },
                "mux": {
                    "enabled": True,
                    "xudpConcurrency": 128,
                    "concurrency": 50,
                    "xudpProxyUDP443": "allow"
                }
            }
        ]
    }

    return v2ray_config


def test_v2ray_config(link):
    httpport = find_free_port()
    socksport = find_free_port()
    filename = ''.join(random.choices(string.ascii_letters + string.digits, k=7)) + '.json'
    # save_config_to_file(generate_v2ray_config(link, port), filename)

    file = convert_uri_json(uri=link, port=httpport, socksport=socksport)

    print(f"Saved config to {file}")
    return get_delay(file, socksport)


def stream_output(pipe, name):
    with pipe:
        for line in iter(pipe.readline, ''):
            if line:  # Only print non-empty lines
                print(f'[{name}] {line.strip()}')


def get_delay(config, port):
    # Start v2ray client with the generated config
    path = './' + config
    # path = '"D:\\projects\\vpn\\configs\\f665d4d2.json"'
    print(path)

    process = subprocess.Popen(
        ["./xray/xray", "run", '-config=' + path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True  # Ensures the output is text rather than bytes
    )

    # Start threads to read stdout and stderr
    threading.Thread(target=stream_output, args=(process.stdout, 'STDOUT')).start()
    threading.Thread(target=stream_output, args=(process.stderr, 'STDERR')).start()

    time.sleep(0.3)  # Allow some time for v2ray to start

    try:
        # Test connectivity to google.com
        start_time = time.time()
        result = requests.get('http://google.com', proxies={
            'http': 'socks5://localhost:' + str(port),
            'https': 'socks5://localhost:' + str(port)
        })

        end_time = time.time()

        # Stop v2ray client
        process.terminate()

        if result and result.status_code == 200:
            delay = (end_time - start_time) * 1000  # Convert to milliseconds
            return delay
        else:
            return None
    except Exception as e:
        print(e)
        process.terminate()
        return None


def save(config, filename="config.json"):
    with open(filename, "w", encoding='utf-8') as file:
        json.dump(config, file, ensure_ascii=False, indent=4)


def fetch_and_decode(urls):
    combined_data = []

    for url in urls:
        # Fetch the data from the URL
        response = requests.get(url)
        response.raise_for_status()  # Ensure we notice bad responses

        # Decode the data from base64
        decoded_data = base64.b64decode(response.content).decode('utf-8')

        # Split the data into lines and extend the combined_data list
        lines = decoded_data.splitlines()
        combined_data.extend(lines)

    return combined_data


def get_configs_sorted():
    mci_urls = [
        "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mci/sub_1.txt",
        "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mci/sub_2.txt",
        "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mci/sub_3.txt",
        "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mci/sub_4.txt",
    ]

    mtn_urls = [
        "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mtn/sub_1.txt",
        "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mtn/sub_2.txt",
        "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mtn/sub_3.txt",
        "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mtn/sub_4.txt",
    ]

    # mci_links = fetch_and_decode(mci_urls)
    mtn_links = fetch_and_decode(mtn_urls + mci_urls)

    results = []

    with ThreadPoolExecutor(max_workers=30) as executor:
        future_to_config = {executor.submit(test_v2ray_config, config): config for config in mtn_links}

        for future in as_completed(future_to_config):
            config = future_to_config[future]
            try:
                print(f"Testing config: {config}")
                delay = future.result()
                if delay is not None:
                    print(f"Connection delay to google.com for {config.split('#')[-1]}: {delay} ms")
                    results.append((config, delay))
                else:
                    print(f"Failed to connect to google.com for {config.split('#')[-1]}")
            except Exception as exc:
                print(f"Generated an exception for {config.split('#')[-1]}: {exc}")

    # Sort results by delay
    sorted_results = sorted(results, key=lambda x: x[1])

    # Print sorted results
    for config, delay in sorted_results:
        print(f"Config: {config.split('#')[-1]}, Delay: {delay} ms")

    # shutil.rmtree('./configs', ignore_errors=True)

    return sorted_results
