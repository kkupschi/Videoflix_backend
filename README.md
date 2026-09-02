# Videoflix Backend

REST API einer Videostreaming Plattform. Sie verwaltet Benutzerkonten mit
Bestätigung per E Mail, verarbeitet hochgeladene Filme im Hintergrund zu
adaptivem HLS Streaming in drei Auflösungen und liefert Manifest und Segmente
an einen Webplayer aus.

Das gesamte System startet mit einem einzigen Befehl als Docker Verbund aus
Anwendungsserver, PostgreSQL, Redis und einem Hintergrundarbeiter.

```
docker compose up --build
```

## Inhalt

- [Architektur](#architektur)
- [Technologiestack](#technologiestack)
- [Technische Entscheidungen](#technische-entscheidungen)
- [Schnellstart](#schnellstart)
- [API Referenz](#api-referenz)
- [Tests](#tests)
- [Projektstruktur](#projektstruktur)
- [Konfiguration](#konfiguration)
- [Stand der Umsetzung](#stand-der-umsetzung)

## Architektur

Vier Dienste, die über ein internes Docker Netzwerk miteinander sprechen. Nach
außen ist ausschließlich der Anwendungsserver auf Port 8000 sichtbar.

```
   Frontend                 ┌──────────────────────────────────┐
   Port 5500                │  web                             │
      │                     │                                  │
      │  REST über JSON     │  Gunicorn                        │
      └────────────────────▶│  Django 5.2 und DRF              │
         HttpOnly Cookies   │  RQ Worker für lange Aufgaben    │
                            │  FFmpeg für die HLS Umwandlung   │
                            └───────┬──────────────────┬───────┘
                                    │                  │
                        ┌───────────▼──────┐   ┌───────▼──────────┐
                        │  db              │   │  redis           │
                        │  PostgreSQL      │   │  Cache und Queue │
                        └──────────────────┘   └──────────────────┘
```

Der Anwendungscontainer beherbergt zwei Prozesse. Gunicorn beantwortet die HTTP
Anfragen, ein RQ Worker arbeitet parallel die Warteschlange ab. Dadurch bleibt
die API auch dann schnell, wenn im Hintergrund ein Film in mehreren Auflösungen
umgerechnet wird.

## Technologiestack

| Bereich | Technologie |
| --- | --- |
| Sprache | Python 3.12 |
| Framework | Django 5.2 |
| API | Django REST Framework |
| Authentifizierung | JSON Web Token in HttpOnly Cookies |
| Datenbank | PostgreSQL |
| Cache und Warteschlange | Redis |
| Hintergrundverarbeitung | Django RQ |
| Videoverarbeitung | FFmpeg, HLS |
| Anwendungsserver | Gunicorn |
| Betrieb | Docker Compose |

## Technische Entscheidungen

**Lange Aufgaben blockieren nie eine Antwort.** Mailversand und Videoumwandlung
laufen als Jobs in einer Redis Warteschlange. Die Registrierung antwortet
sofort, auch wenn der Mailserver langsam ist. Die Umwandlung eines Films in
drei Auflösungen dauert Minuten und läuft vollständig neben dem Webserver.

**Fehlermeldungen verraten nichts über bestehende Konten.** Eine bereits
vergebene Adresse, ein falsches Passwort und eine unbekannte Adresse führen zur
selben allgemeinen Meldung. Das verhindert, dass sich über die API herausfinden
lässt, welche Personen registriert sind.

**Konten sind erst nach Bestätigung nutzbar.** Die Registrierung legt ein
inaktives Konto an und verschickt einen signierten Aktivierungslink. Erst der
Aufruf dieses Links schaltet das Konto frei.

**Token liegen in HttpOnly Cookies.** JavaScript im Browser kommt nicht an die
Token heran, was das Risiko bei Cross Site Scripting deutlich senkt. Der
Abmeldevorgang setzt den Refresh Token zusätzlich auf eine Sperrliste.

**Eigenes Benutzermodell von Anfang an.** Die E Mail Adresse ist eindeutig und
dient als Anmeldename. Das Modell wurde vor der ersten Migration eingeführt,
weil Django es später nur noch mit einer neuen Datenbank austauschen ließe.

**Konfiguration ausschließlich über Umgebungsvariablen.** Im Quelltext steht
kein Geheimnis. Jede Einstellung besitzt einen sinnvollen Standard, das Projekt
startet daher ohne manuelles Nacharbeiten der Konfiguration.

## Schnellstart

Voraussetzung ist eine laufende Docker Installation. Ein lokales Python wird
nicht benötigt, weil die Anwendung vollständig im Container läuft.

```
git clone https://github.com/kkupschi/Videoflix_backend.git
cd Videoflix_backend
cp .env.template .env
docker compose up --build
```

Der Startvorgang sammelt die statischen Dateien ein, führt die Migrationen aus,
legt einen Superuser an und startet danach Worker und Webserver.

| Adresse | Beschreibung |
| --- | --- |
| `http://localhost:8000/api/` | REST API |
| `http://localhost:8000/admin/` | Administration, Pflege der Filme |
| `http://localhost:8000/django-rq/` | Übersicht der Hintergrundjobs |

Die Zugangsdaten des Superusers stammen aus `DJANGO_SUPERUSER_USERNAME` und
`DJANGO_SUPERUSER_PASSWORD`.

## API Referenz

Alle Endpunkte liegen unter `/api/`. Die Video Endpunkte setzen eine gültige
Anmeldung voraus, erkennbar am Zugriffstoken im Cookie.

| Methode | Endpunkt | Zweck | Anmeldung |
| --- | --- | --- | --- |
| `POST` | `/api/register/` | Konto anlegen und Aktivierungsmail auslösen | nein |
| `GET` | `/api/activate/<uidb64>/<token>/` | Konto freischalten | nein |
| `POST` | `/api/login/` | Anmelden, setzt die Token Cookies | nein |
| `POST` | `/api/logout/` | Abmelden, löscht und sperrt die Token | Cookie |
| `POST` | `/api/token/refresh/` | Zugriffstoken erneuern | Cookie |
| `POST` | `/api/password_reset/` | Mail zum Zurücksetzen anfordern | nein |
| `POST` | `/api/password_confirm/<uidb64>/<token>/` | Neues Passwort setzen | nein |
| `GET` | `/api/video/` | Alle Filme mit Titel, Genre und Vorschaubild | ja |
| `GET` | `/api/video/<id>/<aufloesung>/index.m3u8` | HLS Manifest einer Auflösung | ja |
| `GET` | `/api/video/<id>/<aufloesung>/<segment>/` | Einzelnes Videosegment | ja |

### `POST /api/register/`

Legt ein Konto an und stellt den Versand der Aktivierungsmail in die
Warteschlange. Das Konto bleibt inaktiv, bis der Link in der Mail aufgerufen
wurde.

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

| Status | Bedeutung |
| --- | --- |
| `201` | Konto angelegt, Aktivierungsmail in der Warteschlange |
| `400` | Eingabe ungültig, allgemeine Meldung ohne weitere Angaben |

### `GET /api/activate/<uidb64>/<token>/`

Schaltet ein Konto frei. Beide Bestandteile stammen aus dem Link der
Aktivierungsmail. `uidb64` ist die kodierte Kennung des Kontos, `token` ist an
Kennung, Passwort und Adresse gebunden und läuft nach drei Tagen ab.

Antwort `200`

```json
{ "message": "Account successfully activated." }
```

| Status | Bedeutung |
| --- | --- |
| `200` | Konto ist aktiv |
| `400` | Kennung unlesbar, Konto unbekannt oder Token ungültig |

Der Aufruf ist absichtlich wiederholbar. Öffnet jemand denselben Link ein
zweites Mal, etwa weil das Mailprogramm ihn vorab prüft, antwortet der
Endpunkt weiterhin mit `200` statt mit einem Fehler.

### `POST /api/login/`

Prüft die Zugangsdaten und legt beide Token in Cookies ab. Die Antwort enthält
bewusst kein Token, weil der Browser die Cookies selbst mitschickt und
JavaScript sie nicht auslesen kann.

Anfrage

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

Antwort `200`

```json
{
  "detail": "Login successful",
  "user": { "id": 1, "username": "user@example.com" }
}
```

Gesetzte Cookies

| Name | Inhalt | Gültigkeit |
| --- | --- | --- |
| `access_token` | Zugriff auf geschützte Endpunkte | 30 Minuten |
| `refresh_token` | Erneuerung des Zugriffstokens | 1 Tag |

Beide sind `HttpOnly`, tragen `SameSite=Lax` und werden außerhalb der
Entwicklung zusätzlich als `Secure` gesetzt.

| Status | Bedeutung |
| --- | --- |
| `200` | Angemeldet, beide Cookies sind gesetzt |
| `401` | Zugangsdaten falsch oder Konto noch nicht freigeschaltet |

Ein falsches Passwort, eine unbekannte Adresse und ein noch nicht
freigeschaltetes Konto liefern dieselbe Antwort. Von außen ist damit nicht
erkennbar, welcher der drei Fälle vorliegt.

### `POST /api/token/refresh/`

Stellt ein neues Zugriffstoken aus, sobald das alte abgelaufen ist. Der Aufruf
braucht keinen Inhalt, weil der Browser das `refresh_token` Cookie von selbst
mitschickt.

Antwort `200`

```json
{
  "detail": "Token refreshed",
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

| Status | Bedeutung |
| --- | --- |
| `200` | Neues `access_token` Cookie ist gesetzt |
| `400` | Kein `refresh_token` Cookie vorhanden |
| `401` | Refresh Token abgelaufen oder verfälscht |

Erneuert wird ausschließlich das Zugriffstoken. Das Refresh Cookie bleibt
unangetastet und behält seine ursprüngliche Laufzeit, sodass die Sitzung nach
einem Tag zuverlässig endet.

### `POST /api/logout/`

Beendet die Sitzung. Der Aufruf braucht keinen Inhalt. Das Refresh Token wird
auf eine Sperrliste gesetzt und beide Cookies werden im Browser gelöscht.

Antwort `200`

```json
{
  "detail": "Logout successful! All tokens will be deleted. Refresh token is now invalid."
}
```

| Status | Bedeutung |
| --- | --- |
| `200` | Sitzung beendet, beide Cookies gelöscht |
| `400` | Kein `refresh_token` Cookie vorhanden |

Ein bereits unbrauchbares Refresh Token führt trotzdem zu `200`. Wer sich
abmelden will, soll das auch dann können, wenn sein Token schon abgelaufen ist.
Die Cookies verschwinden in jedem Fall.

Das Zugriffstoken selbst bleibt bis zum Ablauf technisch gültig, weil ein JSON
Web Token nicht widerrufbar ist. Praktisch fällt das nicht ins Gewicht, da der
Browser das Cookie sofort verliert und die Laufzeit auf 30 Minuten begrenzt
ist. Dauerhaft entwertet wird das Refresh Token, das die Sitzung sonst immer
weiter verlängern könnte.

## Tests

Die Testsuite prüft das Verhalten der Endpunkte gegen die API Dokumentation,
darunter Statuscodes, Antwortformate, den inaktiven Zustand neuer Konten und
den Inhalt der versendeten Mails.

```
docker compose exec web python manage.py test
```

## Projektstruktur

```
.
├── core/                     Projektkonfiguration
│   ├── settings.py           Einstellungen aus Umgebungsvariablen
│   ├── urls.py               Einstiegspunkt des Routings
│   └── wsgi.py               Schnittstelle zu Gunicorn
├── auth_app/                 Benutzerkonten
│   ├── api/                  Serializer, Views und Routen
│   ├── models.py             Benutzermodell
│   └── utils.py              Mailversand und Hintergrundjobs
├── video_app/                Filme und Streaming
│   ├── api/                  Serializer, Views und Routen
│   └── models.py             Filmmodell
├── templates/emails/         Vorlagen der Systemmails
├── docker-compose.yml        Zusammenspiel der vier Dienste
├── backend.Dockerfile        Abbild des Anwendungscontainers
└── requirements.txt          Abhängigkeiten
```

Die Trennung folgt einer festen Regel. In `views.py` steht ausschließlich, was
eine Antwort zurückgibt. Prüfungen liegen in den Serializern, alles andere in
`utils.py`.

## Konfiguration

| Variable | Bedeutung |
| --- | --- |
| `SECRET_KEY` | Geheimer Schlüssel von Django |
| `DEBUG` | `True` nur in der Entwicklung |
| `ALLOWED_HOSTS` | Kommaliste erlaubter Hostnamen |
| `CSRF_TRUSTED_ORIGINS` | Kommaliste vertrauenswürdiger Ursprünge |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Zugang zu PostgreSQL |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_LOCATION` | Zugang zu Redis |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP Zugang |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | Verschlüsselung des Versands |
| `DEFAULT_FROM_EMAIL` | Absenderadresse |

Optional, jeweils mit sinnvollem Standard.

| Variable | Standard |
| --- | --- |
| `FRONTEND_URL` | erster Eintrag aus `CSRF_TRUSTED_ORIGINS` |
| `CORS_ALLOWED_ORIGINS` | Inhalt von `CSRF_TRUSTED_ORIGINS` |
| `ACTIVATION_URL_TEMPLATE` | Linkvorlage mit `{uid}` und `{token}` |
| `EMAIL_BACKEND` | Konsole, solange kein echter SMTP Server hinterlegt ist |
| `JWT_COOKIE_SECURE` | aktiv, sobald `DEBUG` auf `False` steht |
| `JWT_COOKIE_SAMESITE` | `Lax`, passend zu Frontend und Backend auf einem Host |

Solange in `EMAIL_HOST` der Platzhalter aus der Vorlage steht, schreibt das
Projekt ausgehende Mails in das Containerprotokoll, statt eine Verbindung zu
einem nicht existierenden Server aufzubauen. Sobald dort ein echter Zugang
eingetragen ist, schaltet der Versand automatisch um. So lässt sich der gesamte
Anmeldevorgang ohne eigenes Mailkonto nachvollziehen.

## Stand der Umsetzung

| Bereich | Stand |
| --- | --- |
| Containerbetrieb, Datenbank, Cache, Hintergrundarbeiter | umgesetzt |
| Registrierung mit Aktivierungsmail | umgesetzt |
| Freischaltung des Kontos über den Mail Link | umgesetzt |
| Anmeldung mit Token in HttpOnly Cookies | umgesetzt |
| Erneuerung des Zugriffstokens | umgesetzt |
| Abmeldung mit Sperrliste für das Refresh Token | umgesetzt |
| Passwort zurücksetzen | in Arbeit |
| Filmverwaltung und Auslieferung der Streams | in Arbeit |
| HLS Umwandlung in 480p, 720p und 1080p | in Arbeit |

## Hinweis

Dieses Projekt entstand im Rahmen einer Weiterbildung an der Developer
Akademie. Das Frontend wurde von der Developer Akademie gestellt, dieses
Repository enthält ausschließlich das Backend.
