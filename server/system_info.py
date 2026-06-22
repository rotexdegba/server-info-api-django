import os
import re
import time
import socket
import platform
import subprocess
from datetime import datetime, timezone

import psutil

try:
    import distro as distro_lib
    _HAS_DISTRO = True
except ImportError:
    _HAS_DISTRO = False


def _read_file(path, default=''):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return default


def _run(cmd, default=''):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return default


def bytes_to_human(b, precision=2):
    if b < 0:
        return ''
    for unit in ('B', 'KB', 'MB', 'GB', 'TB', 'PB'):
        if abs(b) < 1024.0:
            return f'{b:.{precision}f} {unit}'
        b /= 1024.0
    return f'{b:.{precision}f} EB'


def _uptime_text(seconds):
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    return f'{days} days, {hours} hours, {minutes} minutes, {secs} seconds'


def _get_distro_name():
    if _HAS_DISTRO:
        name = distro_lib.name(pretty=True)
        if name:
            return name
    raw = _read_file('/etc/os-release')
    for line in raw.splitlines():
        if line.startswith('PRETTY_NAME='):
            return line.split('=', 1)[1].strip().strip('"')
    return platform.version()


def _get_virtualization():
    result = _run(['systemd-detect-virt'], '')
    if result and result.lower() not in ('none', ''):
        return result
    cpuinfo = _read_file('/proc/cpuinfo')
    if 'hypervisor' in cpuinfo.lower():
        return 'Unknown Hypervisor'
    dmi = _read_file('/sys/class/dmi/id/product_name')
    if dmi:
        for virt in ('KVM', 'VirtualBox', 'VMware', 'Xen', 'QEMU', 'Hyper-V'):
            if virt.lower() in dmi.lower():
                return virt
    return ''


def _get_selinux():
    enforce_path = '/sys/fs/selinux/enforce'
    if os.path.exists(enforce_path):
        enforce = _read_file(enforce_path, '0')
        enabled = True
        mode = 'Enforcing' if enforce == '1' else 'Permissive'
        policy = _read_file('/sys/fs/selinux/policyvers', '')
        return {'enabled': enabled, 'mode': mode, 'policy': policy}
    getenforce = _run(['getenforce'], '')
    if getenforce:
        enabled = getenforce.lower() != 'disabled'
        return {'enabled': enabled, 'mode': getenforce, 'policy': ''}
    return {'enabled': -1, 'mode': '', 'policy': ''}


def _get_cpu_info():
    cpuinfo_text = _read_file('/proc/cpuinfo')
    processors = []
    current = {}
    for line in cpuinfo_text.splitlines():
        if line.strip() == '':
            if current:
                processors.append(current)
                current = {}
        elif ':' in line:
            key, _, val = line.partition(':')
            current[key.strip()] = val.strip()
    if current:
        processors.append(current)

    per_cpu_pct = psutil.cpu_percent(percpu=True, interval=0.1)
    freqs = psutil.cpu_freq(percpu=True) or []

    result = []
    physical_processors = [p for p in processors if 'processor' in p]
    for i, pct in enumerate(per_cpu_pct):
        proc = physical_processors[i] if i < len(physical_processors) else {}
        freq = freqs[i].current if i < len(freqs) and freqs[i] else -1.0
        if freq < 0:
            try:
                freq = float(proc.get('cpu MHz', -1))
            except (ValueError, TypeError):
                freq = -1.0
        result.append({
            'cpu_number': i,
            'usage_percentage': pct,
            'vendor': proc.get('vendor_id', ''),
            'model': proc.get('model name', ''),
            'speed_mhz': freq,
        })
    return result


def generate_system_overview():
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    boot_time = psutil.boot_time()
    uptime_secs = time.time() - boot_time

    process_stats = {'running': 0, 'sleeping': 0, 'stopped': 0, 'zombie': 0, 'total': 0, 'threads': 0}
    for p in psutil.process_iter(['status', 'num_threads']):
        try:
            st = p.info['status']
            process_stats['total'] += 1
            process_stats['threads'] += p.info.get('num_threads') or 0
            if st == psutil.STATUS_RUNNING:
                process_stats['running'] += 1
            elif st in (psutil.STATUS_SLEEPING, psutil.STATUS_IDLE):
                process_stats['sleeping'] += 1
            elif st == psutil.STATUS_STOPPED:
                process_stats['stopped'] += 1
            elif st == psutil.STATUS_ZOMBIE:
                process_stats['zombie'] += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    selinux = _get_selinux()
    cpus_info = _get_cpu_info()
    overall_cpu = sum(c['usage_percentage'] for c in cpus_info) / len(cpus_info) if cpus_info else -1.0

    return {
        'host_name': socket.gethostname(),
        'os_family': platform.system(),
        'kernel_version': platform.release(),
        'distro_name': _get_distro_name(),
        'architecture': platform.machine(),
        'system_model': _read_file('/sys/class/dmi/id/product_name'),
        'uptime': int(uptime_secs),
        'uptime_text': _uptime_text(uptime_secs),
        'last_booted_timestamp': int(boot_time),
        'web_software': f'Django {platform.python_version()}',
        'python_version': platform.python_version(),
        'virtualization': _get_virtualization(),
        'total_ram_bytes': mem.total,
        'free_ram_bytes': mem.available,
        'used_ram_bytes': mem.used,
        'total_swap_bytes': swap.total,
        'free_swap_bytes': swap.free,
        'used_swap_bytes': swap.used,
        'overall_cpu_usage_percent': overall_cpu,
        'total_num_physical_cpu_cores': psutil.cpu_count(logical=False) or -1,
        'total_num_virtual_or_logical_processors': psutil.cpu_count(logical=True) or -1,
        'total_number_of_processes': process_stats['total'],
        'total_number_of_threads': process_stats['threads'],
        'total_number_of_running_processes_linux': process_stats['running'],
        'total_number_of_sleeping_processes_linux': process_stats['sleeping'],
        'total_number_of_stopped_processes_linux': process_stats['stopped'],
        'total_number_of_zombie_processes_linux': process_stats['zombie'],
        'number_of_logged_in_users': len(psutil.users()),
        'selinux_enabled': selinux['enabled'],
        'selinux_mode': selinux['mode'],
        'selinux_policy': selinux['policy'],
        'cpus_info': cpus_info,
    }


def generate_cpu_info():
    return _get_cpu_info()


def generate_hardware_info():
    devices = []

    pci_out = _run(['lspci'])
    for line in pci_out.splitlines():
        # format: "<addr> <class>: <vendor> <name>"
        match = re.match(r'^[\da-f:.]+\s+(.+?):\s+(.+)', line, re.IGNORECASE)
        if match:
            class_name = match.group(1).strip()
            rest = match.group(2).strip()
            parts = rest.split(' ', 1)
            vendor = parts[0] if len(parts) > 1 else ''
            name = parts[1] if len(parts) > 1 else rest
            devices.append({'name': name, 'vendor': vendor, 'type': 'PCI'})

    usb_out = _run(['lsusb'])
    for line in usb_out.splitlines():
        # format: "Bus xxx Device xxx: ID xxxx:xxxx Vendor Name"
        match = re.match(r'Bus \d+ Device \d+: ID [\da-f:]+\s+(.*)', line, re.IGNORECASE)
        if match:
            full = match.group(1).strip()
            parts = full.split(' ', 1)
            vendor = parts[0] if len(parts) > 1 else full
            name = parts[1] if len(parts) > 1 else ''
            devices.append({'name': name, 'vendor': vendor, 'type': 'USB'})

    return sorted(devices, key=lambda d: (d['type'], d['name'].lower()))


def generate_sound_card_info():
    cards = []
    cards_raw = _read_file('/proc/asound/cards')
    for line in cards_raw.splitlines():
        match = re.match(r'\s*\d+\s+\[.*?\]:\s+(.+?) - (.+)', line)
        if match:
            vendor = match.group(1).strip()
            name = match.group(2).strip()
            cards.append({'name': name, 'vendor': vendor})
    return sorted(cards, key=lambda c: c['name'].lower())


def generate_disk_drives():
    drives = []
    block_dir = '/sys/block'
    if not os.path.isdir(block_dir):
        return drives

    diskstats = {}
    try:
        for line in _read_file('/proc/diskstats').splitlines():
            parts = line.split()
            if len(parts) >= 14:
                name = parts[2]
                diskstats[name] = {
                    'reads_sectors': int(parts[5]),
                    'writes_sectors': int(parts[9]),
                }
    except Exception:
        pass

    sector_size = 512

    for dev in sorted(os.listdir(block_dir)):
        # skip loop, dm, ram devices
        if re.match(r'^(loop|dm-|ram|zram)', dev):
            continue
        dev_path = os.path.join(block_dir, dev)
        size_path = os.path.join(dev_path, 'size')
        size_sectors = int(_read_file(size_path, '0') or '0')
        size_bytes = size_sectors * sector_size

        vendor = _read_file(os.path.join(dev_path, 'device', 'vendor'))
        model = _read_file(os.path.join(dev_path, 'device', 'model'))

        stats = diskstats.get(dev, {})
        bytes_read = stats.get('reads_sectors', -1) * sector_size if 'reads_sectors' in stats else -1
        bytes_written = stats.get('writes_sectors', -1) * sector_size if 'writes_sectors' in stats else -1

        # partitions
        partitions = []
        for item in sorted(os.listdir(dev_path)):
            if item.startswith(dev) and os.path.isdir(os.path.join(dev_path, item)):
                part_size_sectors = int(_read_file(os.path.join(dev_path, item, 'size'), '0') or '0')
                partitions.append({
                    'name': item,
                    'size_in_bytes': part_size_sectors * sector_size,
                })

        drives.append({
            'name': model or dev,
            'vendor': vendor,
            'device': f'/dev/{dev}',
            'bytes_read': bytes_read,
            'bytes_written': bytes_written,
            'size_in_bytes': size_bytes,
            'partitions': sorted(partitions, key=lambda p: p['name']),
        })

    return sorted(drives, key=lambda d: d['name'].lower())


def generate_disk_mounts():
    mounts = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            mounts.append({
                'name': part.device,
                'mount_point': part.mountpoint,
                'type': part.fstype,
                'size_in_bytes': usage.total,
                'used_bytes': usage.used,
                'free_bytes': usage.free,
                'used_percent': usage.percent,
                'free_percent': round(100.0 - usage.percent, 1),
                'options': [o for o in part.opts.split(',') if o],
            })
        except (PermissionError, OSError):
            mounts.append({
                'name': part.device,
                'mount_point': part.mountpoint,
                'type': part.fstype,
                'size_in_bytes': -1,
                'used_bytes': -1,
                'free_bytes': -1,
                'used_percent': -1,
                'free_percent': -1,
                'options': [o for o in part.opts.split(',') if o],
            })
    return sorted(mounts, key=lambda m: m['name'].lower())


def generate_network_info():
    net_io = psutil.net_io_counters(pernic=True)
    net_stats = psutil.net_if_stats()
    net_addrs = psutil.net_if_addrs()

    result = []
    for iface, stats in sorted(net_stats.items()):
        io = net_io.get(iface)
        addrs = net_addrs.get(iface, [])

        ipv4 = ''
        mac = ''
        for addr in addrs:
            if addr.family.name == 'AF_INET' and not ipv4:
                ipv4 = addr.address
            elif addr.family.name == 'AF_PACKET' and not mac:
                mac = addr.address

        speed_bps = stats.speed * 1_000_000 if stats.speed > 0 else -1

        result.append({
            'name': iface,
            'speed_bits_per_second': speed_bps,
            'type': 'unknown',
            'state': 'up' if stats.isup else 'down',
            'num_bytes_received': io.bytes_recv if io else -1,
            'num_received_errors': io.errin if io else -1,
            'num_received_packets': io.packets_recv if io else -1,
            'num_bytes_sent': io.bytes_sent if io else -1,
            'num_sent_errors': io.errout if io else -1,
            'num_sent_packets': io.packets_sent if io else -1,
            'gateway': '',
            'ipv4': ipv4,
            'mac': mac,
        })
    return sorted(result, key=lambda n: n['name'].lower())


def generate_processes():
    attrs = ['pid', 'name', 'cmdline', 'num_threads', 'status',
             'memory_info', 'username']
    result = []
    for proc in psutil.process_iter(attrs):
        try:
            info = proc.info
            mem = info.get('memory_info')
            cmdline = info.get('cmdline') or []
            result.append({
                'name': info.get('name') or '',
                'command_line': ' '.join(cmdline),
                'num_threads': info.get('num_threads') or 0,
                'state': info.get('status') or '',
                'memory': mem.rss if mem else 0,
                'peak_memory': mem.vms if mem else 0,
                'pid': info.get('pid') or -1,
                'user': info.get('username') or '',
                'io_bytes_read': 0,
                'io_bytes_written': 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Try to get IO stats separately (requires root on many systems)
    pid_map = {p['pid']: p for p in result}
    for proc in psutil.process_iter(['pid']):
        try:
            io = proc.io_counters()
            if proc.pid in pid_map:
                pid_map[proc.pid]['io_bytes_read'] = io.read_bytes
                pid_map[proc.pid]['io_bytes_written'] = io.write_bytes
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return sorted(result, key=lambda p: p['name'].lower())


def generate_services():
    services = []
    out = _run(
        ['systemctl', 'list-units', '--type=service', '--all',
         '--no-legend', '--no-pager', '--plain'],
        ''
    )
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        unit_name = parts[0].removesuffix('.service')
        loaded = parts[1].lower() == 'loaded'
        sub = parts[2].lower()
        active = parts[3].lower()
        started = active == 'active' and sub in ('running', 'exited', 'mounted', 'active', 'listening', 'plugged')
        description = parts[4].strip() if len(parts) > 4 else ''
        services.append({
            'name': unit_name,
            'description': description,
            'loaded': loaded,
            'started': started,
            'state': sub,
        })
    return sorted(services, key=lambda s: s['name'].lower())
