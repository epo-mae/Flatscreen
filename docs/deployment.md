# Deployment and recovery

This document records the production boundary. Local development works now; permanent household deployment starts only after the server, hostname and remote-access method are selected.

## Production shape

Run these components on one maintained household computer:

1. Caddy accepts HTTPS connections on the household hostname.
2. Waitress listens only on `127.0.0.1:8000`.
3. Django owns the SQLite database on a local SSD.
4. A daily timer creates a backup, runs maintenance and reports failures.

Never place the SQLite database on a network share. Do not expose Waitress directly to the network, and do not enable Django’s development setup route in production.

## Required environment

Use `config.settings.production` and set:

- `FLATSCREEN_SECRET_KEY` to a random value at least 50 characters long.
- `FLATSCREEN_ALLOWED_HOSTS` to the exact private hostname.
- `FLATSCREEN_DATA_DIR` to a protected persistent directory on the local SSD.

Generate a secret without putting it in shell history:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
```

Store the environment file so only the service account and administrator can read it. Do not store it in this repository.

## Install and start

After installing dependencies and setting the environment:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\waitress-serve.exe --listen=127.0.0.1:8000 config.wsgi:application
```

The operating-system service must start Waitress after boot, restart it after failure, and use the application directory as its working directory. Caddy must forward only the chosen HTTPS hostname to the loopback listener and serve `/static/` from the generated `staticfiles` directory.

Production setup requires HTTPS. The application trusts `X-Forwarded-Proto` only because Waitress is restricted to loopback and Caddy is the sole upstream proxy.

## Release procedure

For each update:

1. Create and verify a backup.
2. Install pinned dependencies in the isolated environment.
3. Run the tests and the production deployment check.
4. Apply migrations and collect static assets.
5. Restart the application service.
6. Confirm `/health/`, member sign-in and display reconnection.

## Scheduled operations

Run the following daily with visible failure reporting:

```powershell
.\.venv\Scripts\python.exe manage.py backup
.\.venv\Scripts\python.exe manage.py maintenance
```

The current retention policy removes expired pairing attempts, old retry receipts, shopping items more than seven days after removal, activity entries older than 90 days and expired sessions. Backup retention and encryption are handled outside the application because the correct destination depends on household hardware.

Keep seven daily and four weekly encrypted backups, with at least one copy on another physical device or off site.

## Restore drill

Test recovery before entering real household information:

1. Stop the application service.
2. Preserve the current data directory rather than overwriting it.
3. Copy a verified backup to a new protected directory as `flatscreen.sqlite3`.
4. Point a temporary application instance at that directory.
5. Run `manage.py check` and `manage.py migrate --check`.
6. Sign in, read the shopping list and verify a paired test display.
7. Return to the original data directory unless this is a real recovery.

A backup is useful only after this clean restore succeeds.

## Decisions still needed for the household installation

- The always-on computer and its physical location.
- The household hostname and certificate method.
- Whether remote phone access uses a private VPN or a public HTTPS endpoint.
- The encrypted off-device backup destination.
- The browser and kiosk-start method for the actual TV.

These decisions do not change the application model, so feature development can continue while the deployment is being prepared.
