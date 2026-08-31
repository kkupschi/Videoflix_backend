# Videoflix Backend

Backend einer Streaming Plattform nach dem Vorbild von Netflix. Das Projekt stellt
eine REST API bereit, über die das gestellte Frontend Benutzerkonten verwaltet,
Videos auflistet und Videos als HLS Stream abspielt.

## Technologiestack

| Bereich | Technologie |
| --- | --- |
| Framework | Django 5.2 |
| API | Django REST Framework |
| Datenbank | PostgreSQL |
| Cache | Redis |
| Hintergrundjobs | Django RQ |
| Videoverarbeitung | FFmpeg (HLS) |
| Anwendungsserver | Gunicorn |
| Betrieb | Docker Compose |

## Projektstruktur

```
.
├── core/                   Django Projektkonfiguration
│   ├── settings.py         Einstellungen, vollständig über Umgebungsvariablen
│   ├── urls.py             Root URL Konfiguration
│   └── wsgi.py             Einstiegspunkt für Gunicorn
├── backend.Dockerfile      Vom Kurs gestellt, bitte nicht verändern
├── backend.entrypoint.sh   Vom Kurs gestellt, bitte nicht verändern
├── docker-compose.yml      Vom Kurs gestellt, bitte nicht verändern
├── .env.template           Vorlage für die lokale .env Datei
└── requirements.txt        Python Abhängigkeiten
```

## Installation

Voraussetzung ist eine laufende Docker Installation. Ein lokales Python ist nicht
nötig, da die Anwendung vollständig im Container läuft.

1. Repository klonen

   ```
   git clone https://github.com/kkupschi/Videoflix_backend.git
   cd Videoflix_backend
   ```

2. Umgebungsvariablen anlegen

   ```
   cp .env.template .env
   ```

   Anschließend in der `.env` mindestens `SECRET_KEY`, die `DB_` Werte und die
   `EMAIL_` Werte eintragen. Die Datei wird bewusst nicht versioniert.

3. Container starten

   ```
   docker compose up --build
   ```

Der Startvorgang sammelt statische Dateien ein, führt die Migrationen aus, legt
einen Superuser an, startet einen RQ Worker und danach Gunicorn.

## Erreichbarkeit

| Adresse | Beschreibung |
| --- | --- |
| http://localhost:8000/ | API Wurzel |
| http://localhost:8000/admin/ | Django Administration |
| http://localhost:8000/django-rq/ | Übersicht der Hintergrundjobs |

Der Superuser wird beim ersten Start aus `DJANGO_SUPERUSER_USERNAME`,
`DJANGO_SUPERUSER_EMAIL` und `DJANGO_SUPERUSER_PASSWORD` erzeugt.

## Umgebungsvariablen

| Variable | Bedeutung |
| --- | --- |
| `SECRET_KEY` | Geheimer Schlüssel von Django |
| `DEBUG` | `True` nur in der Entwicklung |
| `ALLOWED_HOSTS` | Kommaliste erlaubter Hostnamen |
| `CSRF_TRUSTED_ORIGINS` | Kommaliste vertrauenswürdiger Ursprünge |
| `CORS_ALLOWED_ORIGINS` | Kommaliste der Ursprünge des Frontends |
| `FRONTEND_URL` | Basisadresse des Frontends für Links in E Mails |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Zugang zu PostgreSQL |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_LOCATION` | Zugang zu Redis |
| `ACTIVATION_URL_TEMPLATE` | Linkvorlage der Aktivierungsmail mit `{uid}` und `{token}` |
| `EMAIL_BACKEND` | Versandweg, in der Entwicklung die Konsole |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP Zugang |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | Verschlüsselung des SMTP Versands |
| `DEFAULT_FROM_EMAIL` | Absenderadresse |

## API

### Authentication

#### `POST /api/register/`

Legt ein neues Konto an. Das Konto bleibt inaktiv, bis es über den Link aus der
Aktivierungsmail freigeschaltet wurde. Der Mailversand läuft als Hintergrundjob
über Django RQ, damit die Antwort nicht auf den SMTP Server wartet.

Anfrage

```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "confirmed_password": "securepassword"
}
```

Antwort `201`

```json
{
  "user": { "id": 1, "email": "user@example.com" },
  "token": "activation_token"
}
```

Bei ungültiger Eingabe antwortet der Endpunkt mit `400`. Ob eine Adresse bereits
vergeben ist, wird bewusst nicht verraten. Alle Eingabefehler nutzen dieselbe
allgemeine Meldung.

## Tests

Im laufenden Container

```
docker compose exec web python manage.py test
```

## Entwicklungsstand

| Bereich | Stand |
| --- | --- |
| Grundgerüst, Docker, Datenbank, Cache, Worker | fertig |
| `POST /api/register/` | fertig |
| übrige Authentication Endpunkte | offen |
| Video Endpunkte und HLS Konvertierung | offen |

## Lizenz und Hinweis

Schulungsprojekt der Developer Akademie. Das Frontend wurde von der Developer
Akademie gestellt.
