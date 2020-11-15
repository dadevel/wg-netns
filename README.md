# wg-netns

[wg-quick](https://git.zx2c4.com/wireguard-tools/about/src/man/wg-quick.8) for linux network namespaces.
A simple python script that implements the steps described at [wireguard.com/netns](https://www.wireguard.com/netns/#ordinary-containerization).

## Setup

Requirements:

- Linux
- Python 3.8 or newer
- `ip` from `iproute2`
- `wg` from `wireguard-tools`

Just download the script and make it executable.

~~~ bash
mkdir -p ~/.local/bin/ && curl -o ~/.local/bin/wg-netns https://raw.githubusercontent.com/dadevel/wg-netns/master/wg-netns.py && chmod 0755 ~/.local/bin/wg-netns
~~~

## Usage

~~~
usage: wg-netns [-h] [--wg-dir DIRECTORY] [--netns-dir DIRECTORY] {up,down,status} ...

positional arguments:
  {up,down,status}
    up                  set up interface
    down                tear down interface
    status              show status info

optional arguments:
  -h, --help            show this help message and exit
  --wg-dir DIRECTORY    override WGNETNS_WG_DIR
  --netns-dir DIRECTORY override WGNETNS_NETNS_DIR

environment variables:
  WGNETNS_WG_DIR        wireguard config directory, default: /etc/wireguard
  WGNETNS_NETNS_DIR     network namespace config directory, default: /etc/netns
  WGNETNS_DEBUG         print stack traces
~~~

