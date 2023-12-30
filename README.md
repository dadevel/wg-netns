# wg-netns

[wg-quick](https://git.zx2c4.com/wireguard-tools/about/src/man/wg-quick.8) with support for Linux network namespaces.
A simple Python script that implements the steps described at [wireguard.com/netns](https://www.wireguard.com/netns/#ordinary-containerization).

## Setup

Requirements:

- Python 3.7 or newer
- `ip` from iproute2
- `wg` from wireguard-tools
- optional: [pyyaml](https://pypi.org/project/PyYAML/) python package for configuration files in YAML format, otherwise only JSON is supported

Installation:

a) With [pipx](https://github.com/pypa/pipx).

~~~ bash
pipx install git+https://github.com/dadevel/wg-netns.git@main
~~~

b) With `pip`.

~~~ bash
pip install --user git+https://github.com/dadevel/wg-netns.git@main
~~~

c) As standalone script.

~~~ bash
curl -o ~/.local/bin/wg-netns https://raw.githubusercontent.com/dadevel/wg-netns/main/wgnetns/main.py
chmod +x ~/.local/bin/wg-netns
~~~

## Usage

First, create a configuration profile.
JSON and YAML file formats are supported.

Minimal JSON example:

~~~ json
{
  "name": "ns-example",
  "interfaces": [
    {
      "name": "wg-example",
      "address": ["10.10.10.192/32", "fc00:dead:beef::192/128"],
      "private-key": "4bvaEZHI...",
      "peers": [
        {
          "public-key": "bELgMXGt...",
          "endpoint": "vpn.example.com:51820",
          "allowed-ips": ["0.0.0.0/0", "::/0"]
        }
      ]
    }
  ]
}
~~~

Full YAML example:

~~~ yaml
# name of the network namespace
name: ns-example
# namespace where the interface is initialized, defaults to the main/default namespace
base_netns: null
# if false, the netns itself won't be created or deleted, just the interfaces inside it
managed: true
# list of dns servers, if empty dns servers from default netns will be used
dns-server: [10.10.10.1, 10.10.10.2]
# shell hooks, e.g. to set firewall rules, two formats are supported
pre-up: echo pre-up from managed netns
post-up:
- host-namespace: true
  command: echo post-up from host netns
- host-namespace: false
  command: echo post-up from managed netns
pre-down: echo pre-down from managed netns
post-down: echo post-down from managed netns
# list of wireguard interfaces inside the netns
interfaces:
  # interface name, required
- name: wg-site-a
  # list of ip addresses, at least one entry required
  address:
  - 10.10.11.172/32
  - fc00:dead:beef:1::172/128
  # can also be set via "wg set wg-site-a $key"
  private-key: nFkQQjN+...
  # optional settings
  listen-port: 51821
  fwmark: 21
  mtu: 1420
  # list of wireguard peers
  peers:
    # public key is required
  - public-key: Kx+wpJpj...
    # optional settings
    preshared-key: 5daskLoW...
    endpoint: a.example.com:51821
    persistent-keepalive: 25
    # list of ips the peer is allowed to use, at least one entry required
    allowed-ips:
    - 10.10.11.0/24
    - fc00:dead:beef:1::/64
    # by default the networks specified in 'allowed-ips' are routed over the interface, 'routes' can be used to overwrite this behaivor
    routes:
    - 10.10.11.0/24
    - fc00:dead:beef:1::/64
- name: wg-site-b
  address:
  - 10.10.12.172/32
  - fc00:dead:beef:2::172/128
  private-key: guYPuE3X...
  listen-port: 51822
  fwmark: 22
  peers:
  - public-key: NvZMoyrg...
    preshared-key: cFQuyIX/...
    endpoint: b.example.com:51822
    persistent-keepalive: 25
    allowed-ips:
    - 10.10.12.0/24
    - fc00:dead:beef:2::/64
~~~

Now it's time to setup your new network namespace and all associated wireguard interfaces.

~~~ bash
wg-netns up ./example.yaml
~~~

Profiles stored under `/etc/wireguard/` can be referenced by their name.

~~~ bash
wg-netns up example
~~~

You can verify the success with a combination of `ip` and `wg`.

~~~ bash
ip netns exec ns-example wg show
~~~

You can also spawn a shell inside the netns.

~~~ bash
ip netns exec ns-example bash -i
~~~

### Systemd Service

You can find a `wg-quick@.service` equivalent at [wg-netns@.service](./extras/wg-netns@.service).
Place your profile in `/etc/wireguard/`, e.g. `example.json`, then start the service.

~~~ bash
curl -o /etc/systemd/system/wg-netns@.service https://raw.githubusercontent.com/dadevel/wg-netns/main/extras/wg-netns@.service
systemctl enable --now wg-netns@example.service
~~~

If you are using SELinux, you have to change the SELinux context label, e.g. to `bin_t`, otherwise the service will not find the executable.

~~~ bash
chcon -t bin_t /root/.local/bin/wg-netns
~~~

### Podman Integration

A podman container can be easily attached to a network namespace created by `wg-netns`.
The example below starts a container connected to a netns named *ns-example*.

~~~ bash
podman run -it --rm --network ns:/run/netns/ns-example docker.io/library/alpine wget -q -O - https://ipinfo.io
~~~

### Port Forwarding with Socat

[netns-publish](./extras/netns-publish.sh) is a small wrapper around `socat` that can forward TCP traffic from outside a network namespace to a port inside a network namespace.

Example: All connections to port 1234/tcp in the main/default netns are forwarded to port 5678/tcp in the *ns-example* namespace.

~~~ bash
# terminal 1, create netns and start http server inside
wg-netns up ns-example
echo 'Hello from ns-example!' > ./hello.txt
ip netns exec ns-example python3 -m http.server 5678
# terminal 2, setup port forwarding
./extras/netns-publish.sh 1234 ns-example 127.0.0.1:5678
# terminal 3, test access
curl http://127.0.0.1:1234/hello.txt
~~~

### WireGuard with DynDNS

If your WireGuard server endpoint is a DynDNS domain you can use the [wg-resolve](./extras/wg-resolve/) script to periodically check the connectivity and re-resolve the endpoint if necessary. 

### Firefox in Network Namespace

Start a dedicated Firefox profile with working audio inside the netns created by `wg-netns`.

~~~ bash
sudo ip netns exec ns-example sudo -u "$USER" "HOME=$HOME" "PULSE_SERVER=/run/user/$(id -u)/pulse/native" "PULSE_COOKIE=$HOME/.config/pulse/cookie" firefox -P vpn
~~~
