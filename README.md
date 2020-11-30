# wg-netns

[wg-quick](https://git.zx2c4.com/wireguard-tools/about/src/man/wg-quick.8) for linux network namespaces.
A simple python script that implements the steps described at [wireguard.com/netns](https://www.wireguard.com/netns/#ordinary-containerization).

## Setup

Requirements:

- Linux
- Python 3.7 or newer
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

Or do whatever you want.

### System Service

You can find a `wg-quick@.service` equivalent at [wg-netns@.service](./wg-netns@.service).

### Port Forwarding

Forward TCP traffic from outside a network namespace to a port inside a network namespace with `socat`.

~~~ bash
socat tcp-listen:$LHOST,reuseaddr,fork "exec:ip netns exec $NETNS socat stdio 'tcp-connect:$RHOST',nofork"
~~~

Example: All connections to port 1234/tcp in the main netns are forwarded into the *my-vpn* netns to port 5678/tcp.

~~~ bash
# terminal 1, create netns and start http server inside
wg-netns up my-vpn
echo hello > ./hello.txt
ip netns exec my-vpn python3 -m http.server 5678
# terminal 2, setup port forwarding
socat tcp-listen:1234,reuseaddr,fork "exec:ip netns exec my-vpn socat stdio 'tcp-connect:127.0.0.1:5678',nofork"
# terminal 3, test
curl http://127.0.0.1:1234/hello.txt
~~~

