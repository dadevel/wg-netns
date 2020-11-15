#!/usr/bin/env python3
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from pathlib import Path
import itertools
import os
import subprocess
import sys


def main(args):
    main_parser = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        epilog=(
            'environment variables:\n'
            '  WGNETNS_WG_DIR        wireguard config directory, default: /etc/wireguard\n'
            '  WGNETNS_NETNS_DIR     network namespace config directory, default: /etc/netns\n'
            '  WGNETNS_DEBUG         print stack traces\n'
        ),

    )
    main_parser.add_argument(
        '--wg-dir',
        type=lambda x: Path(x).expanduser(),
        default=os.environ.get('WGNETNS_WG_DIR', '/etc/wireguard'),
        metavar='DIRECTORY',
        help='override WGNETNS_WG_DIR',
    )
    main_parser.add_argument(
        '--netns-dir',
        type=lambda x: Path(x).expanduser(),
        default=os.environ.get('WGNETNS_NETNS_DIR', '/etc/netns'),
        metavar='DIRECTORY',
        help='override WGNETNS_NETNS_DIR',
    )
    subparsers = main_parser.add_subparsers(dest='command', required=True)

    parser = subparsers.add_parser('up', help='set up interface')
    parser.add_argument('name', help='configuration name')

    parser = subparsers.add_parser('down', help='tear down interface')
    parser.add_argument('-f', '--force', help='ignore errors')
    parser.add_argument('name', help='configuration name')

    parser = subparsers.add_parser('status', help='show status info')
    parser.add_argument('name', help='configuration name')

    opts = main_parser.parse_args(args)
    commands = dict(
        up=setup_interface_wrapped,
        down=teardown_interface,
        status=print_status,
    )
    fn = commands[opts.command]
    fn(opts.wg_dir, opts.netns_dir, opts.name)


def print_status(wg_dir, netns_dir, name):
    run('ip', 'netns', 'exec', name, 'wg', 'show', name)


def setup_interface_wrapped(*args):
    try:
        setup_interface(*args)
    except Exception as e:
        teardown_interface(*args, force=True)
        raise


def setup_interface(wg_dir, netns_dir, name):
    wg_interface, wg_peers = parse_wireguard_config(wg_dir.joinpath(name).with_suffix('.conf'))

    run('ip', 'netns', 'add', name)
    run('ip', 'link', 'add', name, 'type', 'wireguard')
    run('ip', 'link', 'set', name, 'netns', name)
    run(
        'ip', 'netns', 'exec', name,
        'wg', 'set', name, 'listen-port', wg_interface.get('listenport', 0),
    )
    run(
        'ip', 'netns', 'exec', name,
        'wg', 'set', name, 'private-key', '/dev/stdin', stdin=wg_interface['privatekey'],
    )
    for peer in wg_peers:
        run(
            'ip', 'netns', 'exec', name,
            'wg', 'set', name,
            'peer', peer['publickey'],
            'preshared-key', '/dev/stdin',
            'endpoint', peer['endpoint'],
            'persistent-keepalive', peer.get('persistentkeepalive', 0),
            'allowed-ips', '0.0.0.0/0,::/0',
            stdin=peer.get('presharedkey', ''),
        )
    for addr in wg_interface['address']:
        run('ip', '-n', name, '-6' if ':' in addr else '-4', 'address', 'add', addr, 'dev', name)
    run('ip', '-n', name, 'link', 'set', name, 'mtu', wg_interface.get('mtu', 1420))
    run('ip', '-n', name, 'link', 'set', name, 'up')
    run('ip', '-n', name, 'route', 'add', 'default', 'dev', name)

    netns_dir = netns_dir/name
    netns_dir.mkdir(parents=True, exist_ok=True)
    if servers := wg_interface.get('dns'):
        resolvconf = '\n'.join(f'nameserver {server}' for server in servers)
        netns_dir.joinpath('resolv.conf').write_text(resolvconf)


def teardown_interface(wg_dir, netns_dir, name, force=False):
    run('ip', '-n', name, 'route', 'delete', 'default', 'dev', name, check=not force)
    run('ip', '-n', name, 'link', 'set', name, 'down', check=not force)
    run('ip', '-n', name, 'link', 'delete', name, check=not force)
    run('ip', 'netns', 'delete', name, check=not force)

    netns_dir = netns_dir/name
    resolv_conf = netns_dir/'resolv.conf'
    if resolv_conf.exists():
        resolv_conf.unlink()
    try:
        netns_dir.rmdir()
    except OSError:
        pass


def parse_wireguard_config(path):
    with open(path) as file:
        it = iter(
            line.strip()
            for line in file
            if line.strip() and not line.startswith('#')
        )
        interface = dict()
        peers = list()
        try:
            while True:
                line = next(it)
                if line.lower() == '[interface]':
                    it, result = parse_interface(it)
                    interface.update(result)
                elif line.lower() == '[peer]':
                    it, result = parse_peer(it)
                    peers.append(result)
                else:
                    raise ParserError(f'invalid line: {line}')
        except ParserError as e:
            raise ParserError(f'failed to parse wireguard configuration: {e}') from e
        except StopIteration:
            return interface, peers


def parse_interface(it):
    result = dict()
    for line in it:
        if line.lower() in ('[interface]', '[peer]'):
            return itertools.chain((line,), it), result
        key, value = parse_pair(line)
        if key in ('address', 'dns'):
            result[key] = parse_items(value)
        elif key in ('mtu', 'listenport', 'privatekey'):
            result[key] = value
        elif key in ('preup', 'postup', 'predown', 'postdown', 'saveconfig', 'table', 'fwmark'):
            raise ParserError(f'unsupported interface key: {key}')
        else:
            raise ParserError(f'unknown interface key: {key}')
    return iter(()), result


def parse_peer(it):
    result = dict()
    for line in it:
        if line.lower() in ('[interface]', '[peer]'):
            return itertools.chain((line,), it), result
        key, value = parse_pair(line)
        if key == 'allowedips':
            result[key] = parse_items(value)
        elif key in ('presharedkey', 'publickey', 'endpoint', 'persistentkeepalive'):
            result[key] = value
        else:
            raise ParserError(f'unknown peer key: {key}')
    return iter(()), result


def parse_pair(line):
    pair = line.split('=', maxsplit=1)
    if len(pair) != 2:
        raise ParserError(f'invalid pair: {line}')
    key, value = pair
    return key.strip().lower(), value.strip()


def parse_items(text):
    return [item.strip() for item in text.split(',')]


def run(*args, stdin=None, check=False):
    args = [str(item) for item in args if item is not None]
    process = subprocess.run(
        args,
        input=stdin,
        text=True,
        check=check,
    )


class ParserError(Exception):
    pass


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
        sys.exit(0)
    except Exception as e:
        if os.environ.get('WGNETNS_DEBUG'):
            raise
        print(f'error: {e} ({e.__class__.__name__})', file=sys.stderr)
        sys.exit(2)

