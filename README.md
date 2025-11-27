# Work Agent

Prozess-Management-Tool für Arbeitsabläufe.

## Status

**Aktiv** - Deployed auf `workagent.weshould.de`

## Features

- User-Verwaltung mit Rollen (Admin/User)
- Prozesse anlegen, bearbeiten, zuweisen
- Status-Workflow (offen → in Bearbeitung → erledigt)
- Prioritäten (niedrig, normal, hoch, kritisch)
- Hierarchische Prozesse (Parent/Child)
- Login-Log für Sicherheit

## Tech Stack

- **Backend**: Python FastAPI
- **Frontend**: Vanilla HTML/CSS/JS
- **Datenbank**: PostgreSQL (`work_agent` DB in generic_db)
- **Auth**: Session-basiert mit bcrypt
- **Deployment**: Docker + Traefik

## Server-Pfade

```
/opt/work-agent/
├── main.py              # FastAPI App
├── index.html           # Dashboard (root)
├── style.css            # Styles (root)
├── static/
│   ├── index.html       # Dashboard
│   ├── login.html       # Login-Seite
│   ├── users.html       # User-Verwaltung
│   ├── log.html         # Login-Log
│   └── style.css        # Styles
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Deployment

```bash
cd /opt/work-agent
docker compose down && docker compose up -d --build
```

## API-Endpunkte

- `POST /api/login` - Login
- `POST /api/logout` - Logout
- `GET /api/me` - Aktueller User
- `GET /api/processes` - Prozesse auflisten
- `POST /api/processes` - Prozess erstellen
- `PUT /api/processes/{id}` - Prozess aktualisieren
- `DELETE /api/processes/{id}` - Prozess löschen
- `GET /api/users` - User auflisten (Admin)
- `POST /api/users` - User erstellen (Admin)

## Datenbank-Tabellen

- `users` - Benutzer mit Rollen
- `processes` - Prozesse/Aufgaben
- `login_log` - Login-Versuche
