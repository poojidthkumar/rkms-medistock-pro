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
