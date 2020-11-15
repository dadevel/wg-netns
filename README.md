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

Instead of running `wg-quick up my-vpn` run `wg-netns up my-vpn`.

Now you can spawn a shell in the new network namespace.

~~~ bash
ip netns exec my-vpn bash -i
~~~

Or connect a container to it.

~~~ bash
podman run -it --rm --network ns:/var/run/netns/my-vpn alpine wget -O - https://ipinfo.io
~~~

You can find a `wg-quick@.service` equivalent at [extras/systemd/wg-netns@.service](./extras/systemd/wg-netns@.service).

