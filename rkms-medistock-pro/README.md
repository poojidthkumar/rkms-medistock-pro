# RKMS MediStock Pro

Hostel medical stock management system (medicines, doctors, students,
dispensing, history, notices, activity log) with a FastAPI + SQLite backend.

## Install (once, needs internet)
```bash
pip install git+https://github.com/YOURUSERNAME/rkms-medistock-pro.git
```

## Run (works offline after install, from any folder)
```bash
rkms-medistock
```
This starts a local server and opens the app in your browser automatically —
same pattern as `jupyter notebook`. A `rkms_medistock.db` file is created in
whichever folder you run the command from; that's your data.

Default logins: `admin` / `admin123`, `doctor` / `doc123`, `nurse` / `nurse123`.

Press `CTRL+C` in the terminal window to stop the server.

## Sharing one database across multiple laptops (network mode)

By default each laptop has its own separate SQLite file. If you want
several laptops on the same WiFi/network to see and edit the *same*
data (medicines, students, history, etc.), set up ONE central computer
to run the server with a shared PostgreSQL database. Other laptops
don't install anything — they just open a browser.

### On the central computer (do this once)

1. Install PostgreSQL: https://www.postgresql.org/download/ (remember
   the password you set for the `postgres` user during install).
2. Open a terminal and create a database and user for the app:
   ```bash
   psql -U postgres
   CREATE DATABASE rkms_medistock;
   CREATE USER rkms_user WITH PASSWORD 'yourpassword';
   GRANT ALL PRIVILEGES ON DATABASE rkms_medistock TO rkms_user;
   \q
   ```
3. Install the app with PostgreSQL support:
   ```bash
   pip install "git+https://github.com/poojidthkumar/rkms-medistock-pro.git#subdirectory=rkms-medistock-pro"
   pip install psycopg2-binary
   ```
4. Find this computer's LAN IP address:
   - Windows: `ipconfig` → look for "IPv4 Address" (e.g. `192.168.1.5`)
5. Set two environment variables and start the server (Windows cmd):
   ```bash
   set RKMS_DATABASE_URL=postgresql://rkms_user:yourpassword@localhost:5432/rkms_medistock
   set RKMS_HOST=0.0.0.0
   rkms-medistock
   ```
6. Allow the port through Windows Firewall if prompted (or manually
   allow TCP port 8000 for Public/Private networks).
7. Keep this terminal window open — this computer is now the server
   for everyone.

### On every other laptop (no install needed)

Just open a browser and go to:
```
http://<central computer's LAN IP>:8000
```
For example: `http://192.168.1.5:8000`. Everyone sees and edits the
same live data. Make sure all laptops are on the same WiFi/network as
the central computer.

### Notes
- If the central computer restarts, you must re-run steps 5 (set the
  two variables and run `rkms-medistock` again) — variables set with
  `set` don't persist across terminal sessions. To make it permanent,
  set them under Windows "Environment Variables" instead of `set`.
- Backup: use `pg_dump` for PostgreSQL backups (the in-app "Download
  Backup" JSON export also still works in network mode).
- Going back to single-laptop mode: just don't set `RKMS_DATABASE_URL`
  — it falls back to the local SQLite file automatically.

