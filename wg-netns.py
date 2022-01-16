#!/usr/bin/env python3
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from pathlib import Path
import json
import os
import re
import subprocess
import sys

NETNS_CONFIG_DIR = '/etc/netns'
DEBUG_LEVEL = 0
SHELL = '/bin/sh'


def main(args):
    global NETNS_CONFIG_DIR
    global DEBUG_LEVEL
    global SHELL

    entrypoint = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        epilog=(
            'environment variables:\n'
            f'  NETNS_CONFIG_DIR    network namespace config directory, default: {NETNS_CONFIG_DIR}\n'
            f'  DEBUG_LEVEL         print stack traces, default: {DEBUG_LEVEL}\n'
            f'  SHELL               program for execution of shell hooks, default: {SHELL}\n'
        ),
    )

    subparsers = entrypoint.add_subparsers(dest='action', required=True)

    parser = subparsers.add_parser('up', help='setup namespace and associated interfaces')
    parser.add_argument('profile', type=lambda x: Path(x).expanduser(), help='path to profile')

    parser = subparsers.add_parser('down', help='teardown namespace and associated interfaces')
    parser.add_argument('-f', '--force', action='store_true', help='ignore errors')
    parser.add_argument('-n', '--keep-namespace', action='store_true', help='keep the namespace')
    parser.add_argument('profile', type=lambda x: Path(x).expanduser(), help='path to profile')

    opts = entrypoint.parse_args(args)

    try:
        NETNS_CONFIG_DIR = Path(os.environ.get('NETNS_CONFIG_DIR', NETNS_CONFIG_DIR))
        DEBUG_LEVEL = int(os.environ.get('DEBUG_LEVEL', DEBUG_LEVEL))
        SHELL = Path(os.environ.get('SHELL', SHELL))
    except Exception as e:
        raise RuntimeError(f'failed to load environment variable: {e} (e.__class__.__name__)') from e

    if opts.action == 'up':
        setup_action(opts.profile)
    elif opts.action == 'down':
        teardown_action(opts.profile, check=not opts.force, keep_namespace=opts.keep_namespace)
    else:
        raise RuntimeError('congratulations, you reached unreachable code')


def setup_action(path):
    namespace = profile_read(path)
    namespace_exist = namespace_exists(namespace)
    try:
        namespace_setup(namespace)
    except KeyboardInterrupt:
        namespace_teardown(namespace, check=False, keep_namespace=namespace_exist)
    except Exception as e:
        namespace_teardown(namespace, check=False, keep_namespace=namespace_exist)
        raise


def teardown_action(path, check=True, keep_namespace=False):
    namespace = profile_read(path)
    namespace_teardown(namespace, check=check, keep_namespace=keep_namespace)


def profile_read(path):
    with open(path) as file:
        return json.load(file)


def namespace_setup(namespace):
    if namespace.get('pre-up'):
        ip_netns_shell(namespace['pre-up'], netns=namespace)
    if not namespace_exists(namespace):
        namespace_create(namespace)
    namespace_resolvconf_write(namespace)
    for interface in namespace['interfaces']:
        interface_setup(interface, namespace)
    if namespace.get('post-up'):
        ip_netns_shell(namespace['post-up'], netns=namespace)


def namespace_get_list_of_existing():
    ip_list = ip('netns', 'list', capture=True).splitlines()
    rg = re.compile('(?P<name>[^ ]*)(?: \(id: (?P<id>\d+)\))?')
    existing_namespaces = dict()
    for line in ip_list:
        match = rg.fullmatch(line)
        if match:
            existing_namespaces[match.group("name")] = match.group("id")
    return existing_namespaces


def namespace_exists(namespace):
    existing_namespaces = namespace_get_list_of_existing()
    return namespace['name'] in existing_namespaces


def namespace_create(namespace):
    ip('netns', 'add', namespace['name'])
    ip('-n', namespace['name'], 'link', 'set', 'dev', 'lo', 'up')


def namespace_resolvconf_write(namespace):
    content = '\n'.join(f'nameserver {server}' for server in namespace.get('dns-server', ()))
    if content:
        NETNS_CONFIG_DIR.joinpath(namespace['name']).mkdir(parents=True, exist_ok=True)
        NETNS_CONFIG_DIR.joinpath(namespace['name']).joinpath('resolv.conf').write_text(content)


def namespace_teardown(namespace, check=True, keep_namespace=False):
    if namespace.get('pre-down'):
        ip_netns_shell(namespace['pre-down'], netns=namespace)
    for interface in namespace['interfaces']:
        interface_teardown(interface, namespace)
    if not keep_namespace:
        namespace_delete(namespace)
    namespace_resolvconf_delete(namespace)
    if namespace.get('post-down'):
        ip_netns_shell(namespace['post-down'], netns=namespace)


def namespace_delete(namespace, check=True):
    ip('netns', 'delete', namespace['name'], check=check)


def namespace_resolvconf_delete(namespace):
    path = NETNS_CONFIG_DIR/namespace['name']/'resolv.conf'
    if path.exists():
        path.unlink()
    try:
        NETNS_CONFIG_DIR.rmdir()
    except OSError:
        pass


def interface_setup(interface, namespace):
    interface_create(interface, namespace)
    interface_configure_wireguard(interface, namespace)
    for peer in interface['peers']:
        peer_setup(peer, interface, namespace)
    interface_assign_addresses(interface, namespace)
    interface_bring_up(interface, namespace)
    interface_create_routes(interface, namespace)


def interface_create(interface, namespace):
    ip('link', 'add', interface['name'], 'type', 'wireguard')
    ip('link', 'set', interface['name'], 'netns', namespace['name'])


def interface_configure_wireguard(interface, namespace):
    wg('set', interface['name'], 'listen-port', interface.get('listen-port', 0), netns=namespace)
    wg('set', interface['name'], 'fwmark', interface.get('fwmark', 0), netns=namespace)
    wg('set', interface['name'], 'private-key', '/dev/stdin', stdin=interface['private-key'], netns=namespace)


def interface_assign_addresses(interface, namespace):
    for address in interface['address']:
        ip('-n', namespace['name'], '-6' if ':' in address else '-4', 'address', 'add', address, 'dev', interface['name'])


def interface_bring_up(interface, namespace):
    ip('-n', namespace['name'], 'link', 'set', 'dev', interface['name'], 'mtu', interface.get('mtu', 1420), 'up')


def interface_create_routes(interface, namespace):
    for peer in interface['peers']:
        networks = peer['routes'] if 'routes' in peer else peer.get('allowed-ips', ())
        for network in networks:
            ip('-n', namespace['name'], '-6' if ':' in network else '-4', 'route', 'add', network, 'dev', interface['name'])


def interface_teardown(interface, namespace, check=True):
    ip('-n', namespace['name'], 'link', 'set', interface['name'], 'down', check=check)
    ip('-n', namespace['name'], 'link', 'delete', interface['name'], check=check)


def peer_setup(peer, interface, namespace):
    options = [
        'peer', peer['public-key'],
        'preshared-key', '/dev/stdin' if peer.get('preshared-key') else '/dev/null',
        'persistent-keepalive', peer.get('persistent-keepalive', 0),
    ]
    if peer.get('endpoint'):
        options.extend(('endpoint', peer.get('endpoint')))
    if peer.get('allowed-ips'):
        options.extend(('allowed-ips', ','.join(peer['allowed-ips'])))
    wg('set', interface['name'], *options, stdin=peer.get('preshared-key'), netns=namespace)


def wg(*args, **kwargs):
    return ip_netns_exec('wg', *args, **kwargs)


def ip_netns_shell(*args, **kwargs):
    return ip_netns_exec(SHELL, '-c', *args, **kwargs)


def ip_netns_exec(*args, netns=None, **kwargs):
    return ip('netns', 'exec', netns['name'], *args, **kwargs)


def ip(*args, **kwargs):
    return run('ip', *args, **kwargs)


def run(*args, stdin=None, check=True, capture=False):
    args = [str(item) if item is not None else '' for item in args]
    if DEBUG_LEVEL:
        print('>', ' '.join(args), file=sys.stderr)
    process = subprocess.run(args, input=stdin, text=True, capture_output=capture)
    if check and process.returncode != 0:
        error = process.stderr.strip() if process.stderr else f'exit code {process.returncode}'
        raise RuntimeError(f'subprocess failed: {" ".join(args)}: {error}')
    return process.stdout


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
        sys.exit(0)
    except Exception as e:
        if DEBUG_LEVEL:
            raise
        print(f'error: {e} ({e.__class__.__name__})', file=sys.stderr)
        sys.exit(2)
