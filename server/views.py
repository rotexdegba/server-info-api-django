import json
from datetime import datetime, timezone

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.shortcuts import redirect, render

from tokens.models import Token, TokenUsage
from . import system_info as si


# ── helpers ──────────────────────────────────────────────────────────────────

def _api_response(data, status_code):
    STATUS_DESC = {
        200: 'Ok',
        401: 'Unauthorized',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        429: 'Too Many Requests. Token has exceeded the maximum allowable requests assigned to it for one day. Try again after 24 hours.',
        500: 'Internal Server Error',
    }
    payload = {
        'status_code': status_code,
        'status_desc': STATUS_DESC.get(status_code, 'Unknown'),
        'data': data if status_code == 200 else [],
        'time_generated': datetime.now(timezone.utc).isoformat(),
    }
    return JsonResponse(payload, status=status_code, safe=False)


def _get_token(request):
    token_str = request.GET.get('token')
    if not token_str:
        return None
    return Token.objects.filter(token=token_str).first()


def _has_valid_token(request):
    tok = _get_token(request)
    return tok is not None and not tok.is_expired()


def _can_access_api(request):
    return request.user.is_authenticated or _has_valid_token(request)


def _log_token_usage(request, status_code):
    tok = _get_token(request)
    if not tok:
        return
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', 'NOIP')
    )
    STATUS_DESC = {
        401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found',
        405: 'Method Not Allowed', 429: 'Too Many Requests', 500: 'Internal Server Error',
    }
    TokenUsage.objects.create(
        token=tok,
        request_uri=request.path,
        request_full_details=f'{request.method} {request.get_full_path()}',
        requesters_ip=ip,
        http_status_code=str(status_code),
        request_error_details=STATUS_DESC.get(status_code, '') if status_code != 200 else '',
    )


def _api_status_code(request):
    if not _can_access_api(request):
        return 401
    if request.method != 'GET':
        return 405
    if not request.user.is_authenticated:
        tok = _get_token(request)
        if tok and tok.has_exceeded_daily_limit():
            return 429
    return 200


def _api_view(request, data_fn):
    status = _api_status_code(request)
    data = data_fn() if status == 200 else []
    _log_token_usage(request, status)
    return _api_response(data, status)


# ── web views ─────────────────────────────────────────────────────────────────

def index(request):
    overview = si.generate_system_overview()
    last_booted = datetime.fromtimestamp(overview['last_booted_timestamp'], tz=timezone.utc)

    ctx = {
        'hostName':             {'label': 'Host Name',               'value': overview['host_name']},
        'distroNameAndVersion': {'label': 'Distro Name and Version', 'value': overview['distro_name']},
        'kernelVersion':        {'label': 'Kernel Version',          'value': overview['kernel_version']},
        'osFamily':             {'label': 'OS Family',               'value': overview['os_family']},
        'architecture':         {'label': 'Architecture',            'value': overview['architecture']},
        'machineModel':         {'label': 'Machine Model',           'value': overview['system_model']},
        'webSoftware':          {'label': 'Web Server Software',     'value': overview['web_software']},
        'pythonVersion':        {'label': 'Python Version',          'value': overview['python_version']},
        'virtualization':       {'label': 'Virtualization Technology', 'value': overview['virtualization']},
        'selinuxEnabled':       {'label': 'Selinux Enabled',         'value': overview['selinux_enabled']},
        'selinuxMode':          {'label': 'Selinux Mode',            'value': overview['selinux_mode']},
        'selinuxPolicy':        {'label': 'Selinux Policy',          'value': overview['selinux_policy']},
        'totalRamBytes':        {'label': 'Ram Memory Usage',        'value': overview['total_ram_bytes']},
        'totalSwapBytes':       {'label': 'Swap Memory Usage',       'value': overview['total_swap_bytes']},
        'usedRamBytes':         {'label': 'Used Ram Memory',         'value': overview['used_ram_bytes']},
        'usedSwapBytes':        {'label': 'Used Swap Memory',        'value': overview['used_swap_bytes']},
        'overallCpuUsagePercent':          {'label': 'Overall CPU Percentage',                      'value': overview['overall_cpu_usage_percent']},
        'totalNumPhyscCpuCores':           {'label': 'Total Number of Physical CPU Cores',           'value': overview['total_num_physical_cpu_cores']},
        'totalNumVirtOrLogicalProcessors': {'label': 'Total Number of Virtual / Logical Processors', 'value': overview['total_num_virtual_or_logical_processors']},
        'lastBootedOn':   {'label': 'Last booted on', 'value': last_booted.strftime('%a, %-d %b %Y %H:%M:%S %Z')},
        'uptime':         {'label': 'Uptime',          'value': overview['uptime_text']},
        'loggedInUsers':  {'label': 'Logged in users', 'value': overview['number_of_logged_in_users'] if overview['number_of_logged_in_users'] > -1 else 'Unknown'},
        'processSummaryInfo': [
            {'label': 'Total Number of Processes',          'value': overview['total_number_of_processes']},
            {'label': 'Total Number of Threads',            'value': overview['total_number_of_threads']},
            {'label': 'Total Number of Running Processes',  'value': overview['total_number_of_running_processes_linux']},
            {'label': 'Total Number of Sleeping Processes', 'value': overview['total_number_of_sleeping_processes_linux']},
            {'label': 'Total Number of Stopped Processes',  'value': overview['total_number_of_stopped_processes_linux']},
            {'label': 'Total Number of Zombie Processes',   'value': overview['total_number_of_zombie_processes_linux']},
        ],
        'cpuInfo': [],
    }

    for cpu in overview['cpus_info']:
        ctx['cpuInfo'].append({
            'cpu_number':       {'label': 'CPU Core Number', 'value': cpu['cpu_number']},
            'usage_percentage': {'label': 'Percent Usage',   'value': cpu['usage_percentage']},
            'vendor':           {'label': 'Vendor',          'value': cpu['vendor']},
            'model':            {'label': 'Model',           'value': cpu['model']},
            'speed_mhz':        {'label': 'Speed',           'value': f"{round(cpu['speed_mhz'] / 1000, 2)} GHz" if cpu['speed_mhz'] > 0 else ''},
        })

    if request.user.is_authenticated:
        ctx['hwInfo']         = sorted(si.generate_hardware_info(), key=lambda d: (d['type'], d['name'].lower()))
        ctx['sCardInfo']      = sorted(si.generate_sound_card_info(), key=lambda d: d['name'].lower())
        network_raw = si.generate_network_info()
        for n in network_raw:
            n['speed_gbps'] = round(n['speed_bits_per_second'] / 1_000_000_000, 3) if n['speed_bits_per_second'] > 0 else ''
        ctx['networkInfo'] = sorted(network_raw, key=lambda d: d['name'].lower())
        ctx['diskDrivesInfo'] = sorted(si.generate_disk_drives(), key=lambda d: d['name'].lower())
        ctx['diskMountsInfo'] = sorted(si.generate_disk_mounts(), key=lambda d: d['name'].lower())
        procs = si.generate_processes()
        for p in procs:
            p['memory']          = max(p['memory'], 0)
            p['peak_memory']     = max(p['peak_memory'], 0)
            p['io_bytes_read']   = max(p['io_bytes_read'], 0)
            p['io_bytes_written']= max(p['io_bytes_written'], 0)
        ctx['processesInfo'] = procs
        svcs = si.generate_services()
        for s in svcs:
            s['loaded']  = 'Yes' if s['loaded'] else 'No'
            s['started'] = 'Yes' if s['started'] else 'No'
        ctx['servicesInfo'] = svcs

    return render(request, 'server/index.html', ctx)


def login_view(request):
    error = ''
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get('next') or '/')
        error = 'Invalid username or password.'
    return render(request, 'registration/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('/')


# ── JSON API endpoints ─────────────────────────────────────────────────────────

def api_server_overview(request):
    return _api_view(request, si.generate_system_overview)


def api_cpus_info(request):
    return _api_view(request, si.generate_cpu_info)


def api_hardware_info(request):
    return _api_view(request, si.generate_hardware_info)


def api_sound_card_info(request):
    return _api_view(request, si.generate_sound_card_info)


def api_disk_drives_info(request):
    return _api_view(request, si.generate_disk_drives)


def api_disk_mounts_info(request):
    return _api_view(request, si.generate_disk_mounts)


def api_network_info(request):
    return _api_view(request, si.generate_network_info)


def api_processes(request):
    return _api_view(request, si.generate_processes)


def api_services(request):
    return _api_view(request, si.generate_services)
