# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Django reverse-engineering of the PHP [linux-server-info-api](https://github.com/rotexdegba/linux-server-info-api) project. Displays Linux server information in a Materialize CSS UI and exposes the same data as JSON REST endpoints. Requires `/proc` and `/sys` to be readable by Python.

Default credentials: **admin / admin** and **root / root**.

## Setup

```bash
# Install dependencies (system Python, no venv available)
~/.local/bin/pip install django psutil distro --break-system-packages

# Apply migrations
python3 manage.py migrate

# Create default users (idempotent)
python3 manage.py shell -c "
from django.contrib.auth.models import User
for u, p in [('admin','admin'),('root','root')]:
    User.objects.get_or_create(username=u, defaults=dict(is_superuser=True, is_staff=True))[0].set_password(p) or User.objects.get(username=u).save()
"

# Run dev server
python3 manage.py runserver --noreload
```

## Common commands

```bash
# Run all tests
python3 manage.py test

# Run a single test module
python3 manage.py test server.tests

# Make and apply migrations after model changes
python3 manage.py makemigrations && python3 manage.py migrate
```

## Architecture

```
config/         Django project settings and root URLconf
server/
  system_info.py   All system data collection (psutil + /proc + subprocesses)
  views.py         Web views (index, login, logout) + JSON API endpoints
  urls.py          URL routing for / and /server/*
tokens/
  models.py        Token, TokenUsage — mirrors the PHP SQLite schema
  views.py         CRUD for tokens (login-required)
  urls.py          /tokens/* routes
templates/
  base.html              Materialize CSS layout shell
  server/index.html      Main dashboard (public summary + login-gated detail)
  tokens/my_tokens.html  Token management list
  tokens/add_edit.html   Add/edit token form
  registration/login.html Login form
```

## Key design decisions

**Authentication:** Django's built-in session auth replaces PHP vespula_auth. `LOGIN_URL = '/server/login'`.

**System info:** `server/system_info.py` replaces the PHP `linfo`/`ginfo`/`trntv` libraries:
- `psutil` — CPU, memory, swap, disk, network, processes
- `/proc/cpuinfo`, `/proc/asound/cards`, `/proc/diskstats` — hardware detail
- `subprocess` — `lspci`, `lsusb` (hardware), `systemctl list-units` (services), `systemd-detect-virt` (virtualization)
- `distro` package — Linux distro name from `/etc/os-release`

**API access control:** Unauthenticated requests need `?token=<token>` with a non-expired token in the DB. Tokens can have `max_requests_per_day` (0 = unlimited). All API calls are logged to `TokenUsage`.

**API endpoints** (all GET, return `{status_code, status_desc, data, time_generated}`):
- `/server/server-overview`
- `/server/cpus-info`
- `/server/hardware-info`
- `/server/sound-card-info`
- `/server/disk-drives-info`
- `/server/disk-mounts-info`
- `/server/network-info`
- `/server/processes`
- `/server/services`

**Public vs. authenticated UI:** The home page `/` shows a basic server summary to everyone. The full dashboard (CPU cards, disk tables, process/service tables with DataTables) is only rendered when `user.is_authenticated`.
