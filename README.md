# Work Agent

Intelligenter Arbeitsassistent für B2B Räderlager.

## Status

Konzeptphase - Python-Neuaufbau

## Dokumentation

Ausführliche Projektbeschreibung in Notion:
https://www.notion.so/Work-Agent-Python-2b6efd5b0fbd818ea87bfe67502fcef5

## Struktur

```
work-agent/
├── core/                    # Das Gehirn - Business-Logik
│   ├── models/              # Datenmodelle
│   ├── services/            # Module (Prozesse, Daten, Kalender, Wissen)
│   └── engine/              # Trigger-Engine, Eskalation
├── adapters/                # Externe Verbindungen (Email, Jira, ...)
├── api/                     # REST API
├── database/                # PostgreSQL Schema
├── config/                  # Konfiguration
└── tests/                   # Tests
```

## Prinzipien

- Core kennt keine externen Systeme
- Adapter sind austauschbar
- Erweiterbar ohne Programmierer
- Trigger → Aktion
