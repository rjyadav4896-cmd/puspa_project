# CampusCare

A Python student healthcare management system for a college health centre. Includes a responsive browser interface, relational records, document-based healthcare notes, and analytics. All bundled examples are fictional.

## Run the project

Requires Python 3.10 or later. In PowerShell, open the project folder:

```powershell
cd D:\puspa_project
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open **http://127.0.0.1:5000**.

| Login | Value |
|---|---|
| Username | `admin` |
| Initial demo password | `CampusCare123!` |

SQLite tables, a session secret, and sample records are initialized automatically in `data/`. The default account password can be set with `$env:ADMIN_PASSWORD = 'your-password'` **before the first launch**. Setting this variable after initialization does not change an existing password. Run the commands with your own Python executable if you already have Flask installed. Stop the server with Ctrl+C.

## Features

- **Overview:** student counts, today's visits, scheduled appointments, stock alerts, department activity, and shortcuts.
- **Students:** create, search, and edit profiles; record blood group and allergies; review appointment and healthcare-note history.
- **Doctors:** create and edit doctors, specialties, and contact details; view scheduled workload.
- **Appointments:** book 30-minute slots, prevent simultaneous bookings for a doctor or student, complete or cancel visits.
- **Prescriptions:** attach a diagnosis, instructions, and multiple medicines to an appointment. Stock is deducted atomically and the appointment is completed. Failed dispensing rolls back the entire prescription.
- **Medicines:** inventory by named batch, expiry and reorder alerts, and restocking of an existing batch.
- **Healthcare records:** flexible document notes, author and timestamps, student filtering, and normalized tags.
- **Analytics:** department visits, monthly trends, doctor workload ranks, dispensed medicine quantities, and note-tag counts.
- **Access controls:** password hashing, authenticated APIs, CSRF tokens, parameterized SQL, escaped UI text, and basic browser security headers.

## SQL and NoSQL modes

**SQL: SQLite** is used in both modes. It requires no separate server.

**NoSQL: MongoDB** is supported for healthcare notes and tag aggregation. To demonstrate the complete SQL + NoSQL database integration, start your MongoDB server and then run:

```powershell
$env:MONGO_URI = 'mongodb://127.0.0.1:27017/'
.\.venv\Scripts\python.exe app.py
```

The database is `campuscare`, collection `health_records`. A configured but unavailable MongoDB server causes startup to fail; it does not silently switch storage. The application creates indexes on student/time and tags, and uses a MongoDB aggregation pipeline for tag analytics.

Without `MONGO_URI`, the app stores notes in `data/health_records.json` using atomic replacement and a process-local lock. **This local demo option is a document file, not a NoSQL database server.** It is suitable for a single application process. The interface identifies the active storage mode. Existing JSON notes are not automatically migrated when switching to MongoDB; start with a fresh project data directory for a clean MongoDB demonstration or migrate notes deliberately.

## Deploying the demonstration to Vercel

`app.py` exports a top-level `app = create_app()` WSGI instance for Vercel's Flask detection. Select Flask as the framework and use this directory as the project root. No custom build command is required.

Set `SECRET_KEY` to a long random value in Vercel's environment variables so sessions remain valid across application instances. Set `ADMIN_PASSWORD` to your chosen administrator password. Redeploy after updating the code or environment variables. Set `MONGO_URI` only when using a reachable MongoDB service.

On Vercel (`VERCEL=1`), local data defaults to the temporary directory instead of the read-only deployment directory. **SQLite and JSON data on Vercel are temporary and instance-local**: changes may disappear after a cold start or deployment, and different instances may have different records. This mode is for demonstrations. MongoDB only persists health notes; it does not make the relational SQLite records persistent. Persistent hosting requires a durable SQL backend as well, or a server with persistent storage. `.vercelignore` excludes local databases, session secrets, and development files from CLI uploads.

## Testing

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use isolated databases under `data/tests/` and cover authentication, CSRF, slot conflicts, transactional dispensing, expiry, cancelled appointments, input validation, document filtering, analytics, editing, and persistence. The automated suite uses JSON mode; a running MongoDB service is needed to verify MongoDB connectivity and aggregation end to end.

## Suggested demonstration

1. Sign in and explain the overview metrics.
2. Create a student, edit an allergy, and open the student's history.
3. Add a doctor or use a sample doctor, then book a future appointment at :00 or :30.
4. Try booking the same doctor or student at the same time to show conflict handling.
5. Create a prescription for the appointment and observe the reduced medicine stock and completed visit.
6. Try dispensing more stock than is available to demonstrate rollback.
7. Add a health record tagged `wellness` and view its count under Analytics.
8. Explain the relational schema, SQL queries, and MongoDB document design in `PROJECT_REPORT.md`.

## Project layout

```text
app.py                   Flask routes, validation, transactions, demo seed
documents.py             MongoDB and local JSON document storage
schema.sql               Relational tables, constraints, indexes, view
templates/index.html     Application shell and login
static/app.js            Forms, API interaction, tables, dashboards
static/style.css         Responsive styling
tests/test_app.py         Automated integration tests
PROJECT_REPORT.md        Architecture, data design, queries, limitations
data/                    Generated local databases and session secret
```

## Scope and limitations

This is a local college-project application with one administrator role. It does not provide patient self-service, appointment reminders, automatic clinical decisions, prescription signing, allergy/drug interaction checking, or a full audit trail. Recorded allergies are informational and must be reviewed by a clinician. Prescription entries describe dispensing; they do not generate clinical advice.

The app uses the server's local time for appointment validation and daily reporting; configure the server to the campus timezone. Prescriptions and health notes are retained rather than destructively deleted. Appointment status changes are final through the UI. Restock only the same batch with the same expiry date; add a distinctly named batch for other expiry dates. Inventory quantities use whole units.

For real student healthcare data, add appropriate role permissions, login rate limits, audit logging, encrypted backups, HTTPS, and institutional privacy controls before deployment. The included Flask server and default credentials are for local demonstrations. Back up SQLite and the document store together while the application is stopped; cross-database consistency relies on stable student IDs and application validation, not distributed transactions.
