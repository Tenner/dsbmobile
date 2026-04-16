# DSBmobile Vertretungsplan – Home Assistant Integration

[![GitHub Release](https://img.shields.io/github/v/release/Tenner/dsbmobile?style=flat-square)](https://github.com/Tenner/dsbmobile/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://github.com/hacs/integration)

Custom Integration für [Home Assistant](https://www.home-assistant.io/), die den Vertretungsplan von [DSBmobile](https://www.dsbmobile.de/) ausliest und als Sensor bereitstellt.

## Features

- Automatischer Abruf des Vertretungsplans über die DSBmobile Web API
- Untis HTML-Parser (`subst_*.htm`) mit Unterstützung für durchgestrichenen Text (~~alt~~ → neu)
- Mehrere Klassen kommagetrennt konfigurierbar (z.B. `08b, 05a`) — pro Klasse ein eigener Sensor
- Klasse nachträglich änderbar über Konfigurieren (Options Flow)
- Verwaiste Sensoren werden beim Entfernen von Klassen automatisch aufgeräumt
- Aktualisierung alle 30 Minuten
- Sensor-State = Anzahl der Vertretungseinträge
- Nicht-HTML-Pläne (Bilder, Dokumente) als `other_plans` Attribut verfügbar
- iso-8859-1 Encoding-Unterstützung für Untis HTML
- Vollständige UI-Konfiguration (kein YAML nötig)
- Deutsche und englische Übersetzung
- Breitbild-Dashboard (3-Spalten Grid, ein Tag pro Spalte)

## Voraussetzungen

- Home Assistant 2024.1 oder neuer
- DSBmobile-Zugangsdaten (Benutzer-ID und Passwort von der Schule)

## Dateistruktur

```
custom_components/dsbmobile/
├── __init__.py            # Integration Setup & Lifecycle
├── const.py               # Konstanten & Defaults
├── dsb_api.py             # Web API Client & Untis HTML-Parser
├── config_flow.py         # UI-Konfiguration (Config Flow + Options Flow)
├── sensor.py              # Sensor-Entity mit DataUpdateCoordinator
├── manifest.json          # HA Integration Manifest
├── strings.json           # UI-Texte (Fallback)
└── translations/
    ├── de.json            # Deutsche Übersetzung
    └── en.json            # Englische Übersetzung
```

---

## Installation

### Manuell

1. Den Ordner `custom_components/dsbmobile/` in das Home Assistant Konfigurationsverzeichnis kopieren:

   ```
   /config/custom_components/dsbmobile/
   ```

   Bei einer typischen Installation liegt das Konfigurationsverzeichnis unter:
   - Home Assistant OS / Supervised: `/config/`
   - Docker: das gemountete Volume, z.B. `/home/homeassistant/.homeassistant/`
   - Core: `~/.homeassistant/`

2. Home Assistant neu starten:
   - Über die UI: **Einstellungen → System → Neustart**
   - Oder per CLI: `ha core restart`

### Über HACS (Custom Repository)

1. In HACS auf die drei Punkte oben rechts klicken → **Benutzerdefinierte Repositories**
2. Repository-URL eingeben: `https://github.com/Tenner/dsbmobile`
3. Kategorie: **Integration**
4. Hinzufügen und installieren
5. Home Assistant neu starten

---

## Einrichtung

1. Nach dem Neustart: **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. Nach `DSBmobile` suchen
3. Zugangsdaten eingeben:

   | Feld          | Beschreibung                                                  | Pflicht |
   |---------------|---------------------------------------------------------------|---------|
   | Benutzer-ID   | Die DSBmobile Kennung (von der Schule erhalten)               | Ja      |
   | Passwort      | Das zugehörige Passwort                                       | Ja      |
   | Klasse(n)     | Kommagetrennt, z.B. `08b` oder `08b, 05a` (leer = alle)      | Nein    |

4. Die Integration prüft die Zugangsdaten sofort. Bei Erfolg werden die Sensoren angelegt.
5. Klasse(n) nachträglich ändern: **Einstellungen → Geräte & Dienste → DSBmobile → Konfigurieren**

---

## Sensor

Pro konfigurierter Klasse wird ein Sensor erstellt:

| Eigenschaft     | Wert                                                |
|-----------------|-----------------------------------------------------|
| Entity-ID       | `sensor.vertretungsplan_08b` (je nach Klasse)       |
| State           | Anzahl der aktuellen Vertretungseinträge (Integer)  |
| Icon            | `mdi:school`                                        |
| Aktualisierung  | Alle 30 Minuten                                     |

### Attribute

| Attribut       | Typ    | Beschreibung                              |
|----------------|--------|-------------------------------------------|
| `class_filter` | String | Die konfigurierte Klasse                  |
| `count`        | Int    | Anzahl der Einträge                       |
| `entries`      | Liste  | Liste aller Vertretungseinträge (Details) |
| `other_plans`  | Liste  | Nicht-HTML-Pläne (Bilder, Dokumente)      |

Jeder Eintrag in `entries` enthält (Untis-Spalten):

| Feld         | Beispiel                    | Beschreibung                          |
|--------------|-----------------------------|---------------------------------------|
| `day`        | `16.4.2026 Donnerstag`      | Tag aus `div.mon_title`               |
| `art`        | `Entfall`                   | Art der Änderung                      |
| `class`      | `08b`                       | Betroffene Klasse(n)                  |
| `lesson`     | `3`                         | Stunde                                |
| `subject`    | `~~Ma~~ De`                 | Fach (durchgestrichen = altes Fach)   |
| `room`       | `A204`                      | Raum                                  |
| `vertr_von`  | `Do-16.4. / 6`              | Vertreten von                         |
| `nach`       | `Entfall für Lehrer`        | (Le.) nach                            |
| `text`       | `Klausur wird geschrieben`  | Zusatztext                            |

---

## Beispiel-Dashboard

Ein fertiges Breitbild-Dashboard (1920x1200) liegt unter [`examples/dashboard.yaml`](examples/dashboard.yaml):

- Mushroom-Header mit Anzahl und Status-Farbe (rot/grün)
- 3-Spalten Grid: ein Tag pro Spalte nebeneinander
- Einträge einzeilig mit beschrifteten Feldern
- Durchgestrichener Text wird als ~~Markdown~~ gerendert
- Verlaufsgraph über 7 Tage

Voraussetzungen: `mushroom-cards` und `layout-card` (beide über HACS).

---

## Beispiel-Automationen

### Push-Benachrichtigung bei neuen Vertretungen

```yaml
automation:
  - alias: "Vertretungsplan Benachrichtigung"
    trigger:
      - platform: state
        entity_id: sensor.vertretungsplan_08b
    condition:
      - condition: numeric_state
        entity_id: sensor.vertretungsplan_08b
        above: 0
    action:
      - service: notify.mobile_app_dein_handy
        data:
          title: "Vertretungsplan"
          message: >
            {{ states('sensor.vertretungsplan_08b') }} Vertretung(en):
            {% for e in state_attr('sensor.vertretungsplan_08b', 'entries') %}
            {{ e.day }} · {{ e.art }} · {{ e.lesson }}. Std · {{ e.subject }} · Raum: {{ e.room }}{% if e.text %} · {{ e.text }}{% endif %}
            {% endfor %}
```

### Tägliche Zusammenfassung morgens um 6:30

```yaml
automation:
  - alias: "Vertretungsplan Morgenbericht"
    trigger:
      - platform: time
        at: "06:30:00"
    condition:
      - condition: numeric_state
        entity_id: sensor.vertretungsplan_08b
        above: 0
    action:
      - service: notify.mobile_app_dein_handy
        data:
          title: "Vertretungsplan heute"
          message: >
            {{ states('sensor.vertretungsplan_08b') }} Änderung(en):
            {% for e in state_attr('sensor.vertretungsplan_08b', 'entries') %}
            {{ e.art }}: {{ e.lesson }}. Std {{ e.subject }} ({{ e.room }}){% if e.text %} – {{ e.text }}{% endif %}
            {% endfor %}
```

---

## Technische Details

### API

Die Integration nutzt die DSBmobile **Web API** — den gleichen Endpoint, den auch die DSBmobile-Webseite verwendet:

1. **Web Login**: `POST https://www.dsbmobile.de/Login.aspx` mit ASP.NET Formular (ViewState, EventValidation)
   → Setzt Session-Cookies

2. **Daten abrufen**: `POST https://www.dsbmobile.de/jhw-*.ashx/GetData` mit gzip-komprimiertem, base64-kodiertem JSON-Payload
   → Gibt komprimierte JSON-Antwort mit allen Plänen, Aushängen und Dokumenten zurück

3. **HTML-Pläne laden**: `GET https://dsbmobile.de/data/.../subst_001.htm` (iso-8859-1 kodiert)
   → Untis-HTML wird mit BeautifulSoup geparst, `<s>` Tags werden zu `~~Strikethrough~~` konvertiert

### Architektur

```mermaid
graph TB
    subgraph Home Assistant
        CF[Config Flow<br><i>config_flow.py</i>]
        OF[Options Flow<br><i>config_flow.py</i>]
        CO[DataUpdateCoordinator<br><i>sensor.py</i>]
        SE1[Sensor Klasse A<br><i>sensor.py</i>]
        SE2[Sensor Klasse B<br><i>sensor.py</i>]
        AU[Automationen]
    end

    subgraph DSBmobile Integration
        API[DSBMobileAPI<br><i>dsb_api.py</i>]
        PA[Untis HTML Parser<br><i>BeautifulSoup + iso-8859-1</i>]
    end

    subgraph DSBmobile Server
        LOGIN[Web Login<br><i>dsbmobile.de/Login.aspx</i>]
        WEBAPI[Web API<br><i>dsbmobile.de/jhw-*.ashx/GetData</i>]
        HTML[Vertretungsplan HTML<br><i>dsbmobile.de/data/.../subst_*.htm</i>]
    end

    CF -->|Zugangsdaten validieren| API
    OF -->|Klassen ändern| CO
    CO -->|alle 30 Min| API
    API -->|1. POST Login + Cookies| LOGIN
    LOGIN -->|Session Cookie| API
    API -->|2. POST gzip+base64| WEBAPI
    WEBAPI -->|JSON mit Plan-URLs| API
    API -->|3. HTML laden| HTML
    HTML -->|Untis HTML iso-8859-1| PA
    PA -->|Alle Einträge ungefiltert| CO
    CO -->|Lokaler Filter| SE1
    CO -->|Lokaler Filter| SE2
    SE1 -->|State + Attribute| AU
    SE2 -->|State + Attribute| AU
```

### Datenfluss

```mermaid
sequenceDiagram
    participant HA as Home Assistant
    participant CO as Coordinator
    participant API as DSBMobileAPI
    participant WEB as dsbmobile.de
    participant HTML as Plan HTML

    HA->>CO: Update (alle 30 Min)
    CO->>API: get_substitutions("")
    API->>WEB: GET /Login.aspx
    WEB-->>API: HTML + ViewState
    API->>WEB: POST /Login.aspx (Credentials)
    WEB-->>API: Session Cookie + Redirect
    API->>WEB: POST /jhw-*.ashx/GetData (gzip+base64)
    WEB-->>API: JSON (komprimiert) mit Plan-URLs
    loop Für jeden HTML-Plan (subst_*.htm)
        API->>HTML: GET /data/.../subst_001.htm
        HTML-->>API: Untis HTML (iso-8859-1)
        API->>API: Decode + Parse (mon_title, mon_list, s-Tags)
    end
    API-->>CO: List[SubstitutionEntry] (alle Klassen)
    CO-->>HA: Sensor 08b filtert lokal
    CO-->>HA: Sensor 05a filtert lokal
```

### Komponentenübersicht

```mermaid
classDiagram
    class DSBMobileAPI {
        -username: str
        -password: str
        -session: aiohttp.ClientSession
        -logged_in: bool
        +last_plans: list~PlanInfo~
        +authenticate() bool
        -_web_login() bool
        -_call_web_api() dict
        +get_plans() list~PlanInfo~
        +get_substitutions(class_filter) list~SubstitutionEntry~
        -_parse_plan_html(html, filter) list~SubstitutionEntry~
        -_cell_text(cell) str
    }

    class PlanInfo {
        +title: str
        +date: str
        +url: str
        +is_html: bool
    }

    class SubstitutionEntry {
        +day: str
        +art: str
        +class_name: str
        +lesson: str
        +subject: str
        +room: str
        +vertr_von: str
        +nach: str
        +text: str
        +raw_text: str
    }

    class DSBDataUpdateCoordinator {
        +api: DSBMobileAPI
        +_async_update_data() list~SubstitutionEntry~
    }

    class DSBVertretungsplanSensor {
        -class_filter: str
        +native_value: int
        +extra_state_attributes: dict
        -_filtered_entries() list~SubstitutionEntry~
    }

    class DSBMobileConfigFlow {
        +async_step_user(user_input) ConfigFlowResult
    }

    class DSBMobileOptionsFlow {
        +async_step_init(user_input) ConfigFlowResult
    }

    DSBMobileAPI --> PlanInfo : erzeugt
    DSBMobileAPI --> SubstitutionEntry : erzeugt
    DSBDataUpdateCoordinator --> DSBMobileAPI : nutzt
    DSBVertretungsplanSensor --> DSBDataUpdateCoordinator : filtert lokal
    DSBMobileConfigFlow --> DSBMobileAPI : validiert mit
    DSBMobileConfigFlow --> DSBMobileOptionsFlow : Options Flow
```

---

## Troubleshooting

| Problem                          | Lösung                                                                 |
|----------------------------------|------------------------------------------------------------------------|
| Integration nicht sichtbar       | HA neu starten, Ordnerstruktur prüfen (`custom_components/dsbmobile/`) |
| "Ungültige Zugangsdaten"         | Benutzer-ID und Passwort auf dsbmobile.de prüfen                       |
| Sensor zeigt 0                   | Klasse exakt wie im Plan eingeben (z.B. `08b` nicht `8b`)             |
| Keine Aktualisierung             | Entwicklerwerkzeuge → Dienste → `homeassistant.update_entity`          |
| Update von v1.x auf v2.x        | Integration löschen und neu einrichten (Auth-Methode geändert)         |
| Klasse ändern                    | Einstellungen → Geräte & Dienste → DSBmobile → Konfigurieren          |
| Fehler im Log                    | Debug-Logging aktivieren (siehe unten)                                 |

### Debug-Logging aktivieren

In `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.dsbmobile: debug
```

---

## Lizenz

MIT License – frei verwendbar und anpassbar.
