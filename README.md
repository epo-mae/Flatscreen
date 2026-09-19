# Flatscreen

Flatscreen is a private shared-household application with a mobile personal interface and a separately paired, read-only household display.

The current foundation includes:

- First-run household and administrator setup.
- Persistent member sessions, administrator/member roles, account deactivation and access revocation.
- A personal profile where each member changes their own display name and password.
- A shared shopping list with quantities, notes, purchased state, duplicate handling, CSV export and short undo support.
- Automatic two-second updates with safe retry IDs and edit conflict detection.
- A dedicated display layout with pairing, revocation, cached last-known state and reconnect behaviour.
- Manual HOME/OUT presence backed by event history and shown on the household display.
- A shared planning area for dinner, temporary notices and upcoming household events.
- A shared chores board with ownership, due dates, upcoming recurrence previews, completion history and repeating responsibilities.
- A TV composition that prioritises tonight, important notices, event countdowns, shopping and presence.
- Today’s local weather with high, low, feels-like temperature, UV guidance and automatic condition alerts.
- A household appearance with five presets (Classic, Minimal, Warm, Contrast, Modern), server-rendered previews, fine-tuning and reset actions, applied to both the personal and display interfaces.
- Activity records, consistent SQLite backups and retention maintenance.

## Run it locally

From PowerShell in this folder:

```powershell
py -m venv .venv
$env:TEMP = Join-Path (Get-Location) '.tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
py -m pip --python .\.venv\Scripts\python.exe install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Open <http://127.0.0.1:8000/> on this computer. The first visit guides you through household setup. The development setup page intentionally rejects access from other devices.

This development server is for local development only. Do not expose it to the home network or internet.

## Pair a display during development

1. Open `/display/` in a separate browser profile or private window.
2. Select **Connect this screen**.
3. On an administrator session, open **Settings** and enter the eight-digit code.
4. The display reconnects with read-only access.

## Verify the foundation

```powershell
.\.venv\Scripts\python.exe manage.py test tests
.\.venv\Scripts\python.exe manage.py check
```

The test suite covers authentication, permissions, display data filtering, pairing and revocation, cross-client visibility, CSRF protection, duplicate requests, stale edits, destructive confirmations, account deactivation and input validation.

## Backups

Create a consistent, integrity-checked backup:

```powershell
.\.venv\Scripts\python.exe manage.py backup
```

Backups contain private household data. Copy verified backups to encrypted storage outside the server. See [deployment and recovery](docs/deployment.md) before using Flatscreen as the household’s real system.

## Project guide

- `config/` — environment settings and URL routing.
- `household/` — members, roles, display devices, settings and activity.
- `shopping/` — shopping data and shared-state actions.
- `templates/` — personal, display, setup and settings interfaces.
- `static/` — the visual system, browser behaviour and display offline shell.
- `tests/` — foundation behaviour and security tests.
- `docs/` — deployment and recovery decisions.
