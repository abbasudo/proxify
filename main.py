import subprocess

import config
import outbound
from config import get_configs_sorted


def restart_service():
    service_name = 'crawler.service'

    try:
        # Restart the service
        subprocess.run(['sudo', 'systemctl', 'restart', service_name], check=True)
        print(f'Successfully restarted {service_name}')
    except subprocess.CalledProcessError as e:
        print(f'Failed to restart {service_name}: {e}')
    except Exception as e:
        print(f'An error occurred: {e}')


if __name__ == '__main__':
    links = get_configs_sorted()[-10:]

    inbound_configs = []
    rules = []
    outbound_configs = []

    for index in range(0, len(links)):
        link = links[index]
        outbound_configs.append(outbound.generate(link[0], "outbound-" + str(index)))
        inbound_configs.append({
            "tag": "inbound-" + str(index),
            "port": 30080 + index,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {
                "auth": "noauth",
                "udp": True,
                "allowTransparent": True
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"],
                "routeOnly": True
            }
        })

        rules.append({
            "type": "field",
            "inboundTag": [
                "outbound-" + str(index)
            ],
            "outboundTag": "inbound-" + str(index)
        }),

    configs = {
        "log": {
            "loglevel": "warning"
        },
        "inbounds": inbound_configs,
        "outbounds": outbound_configs,

        "routing": {
            "rules": rules
        },
    }

    config.save(configs, "./xray/config.json")
    restart_service()
