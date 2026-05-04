# DSNPRU_REG

DSNPRU_REG is a school activity registration system built with FastAPI, SQLAlchemy, Jinja2, Alpine.js, and SQLite. It supports student self-registration, waitlists, team activities, real-time admin updates, exports, announcements, and operational monitoring in a single deployable app.

## Contents

- [Overview](#overview)
- [Feature Summary](#feature-summary)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Waitlist Email Flow](#waitlist-email-flow)
- [Admin Guide](#admin-guide)
- [Student Guide](#student-guide)
- [Routes](#routes)
- [Database Schema](#database-schema)
- [Exports](#exports)
- [Runtime Schema Upgrades](#runtime-schema-upgrades)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)
- [License](#license)

## Overview

This project is designed for school events or club/activity selection where:

- students must be selected from a pre-imported school roster
- activities can have quotas, group restrictions, classroom restrictions, and schedules
- some activities are individual and some are team-based
- over-capacity registrations should go to a waitlist instead of failing completely
- admins need a web dashboard to manage students, activities, announcements, exports, and platform status
- changes should appear in near real-time without a full page refresh

The application is server-rendered with Jinja templates and enhanced on the client with Alpine.js and Axios. Data is stored in `sicday.db`.

## Feature Summary

### Student-facing

- activity browsing with current seat counts
- live updates via WebSocket
- student lookup by name or student number
- self-registration for open activities
- team registration with optional team name and partner lookup
- waitlist support when an activity is full
- email required for waitlist confirmation
- waitlist confirmation email
- promotion email when a waitlisted registration becomes registered
- self-service registration lookup
- self-service cancellation while the activity remains open
- active announcements shown as banners
- urgent announcements shown as modal popups
- dark mode

### Admin-facing

- JWT-based admin authentication
- superuser and non-superuser roles
- dashboard with totals and activity chart
- mail settings page for waitlist email delivery
- activity CRUD
- activity open/close toggle
- activity detail page with per-activity registrations
- activity groups with quotas, visibility, and classroom restrictions
- student import from Excel
- student edit, delete, bulk delete, and bulk classroom update
- announcement management
- analytics page
- platform status and metrics page
- registration export to Excel and PDF
- student export to Excel and PDF
- audit log viewer

### Operational behavior

- SQLite database auto-creation on first run
- runtime schema patching for older databases
- request logging
- periodic system metric logging
- WebSocket broadcasts for activity and announcement refreshes

## Tech Stack

### Backend

- FastAPI
- SQLAlchemy ORM
- Pydantic
- Uvicorn
- SQLite
- FastAPI-Mail

### Frontend

- Jinja2 templates
- Alpine.js
- Axios
- SweetAlert2
- Chart.js
- custom CSS in `frontend/static/css/custom.css`

### Export / file processing

- OpenPyXL
- ReportLab

## Project Structure

```text
DSNPRU_REG/
├── backend/
│   ├── auth.py
│   ├── database.py
│   ├── env_settings.py
│   ├── mail_service.py
│   ├── main.py
│   ├── models.py
│   ├── routers/
│   │   ├── admin.py
│   │   ├── export.py
│   │   └── public.py
│   ├── schemas.py
│   ├── utils.py
│   └── websocket_manager.py
├── frontend/
│   ├── static/
│   │   ├── css/
│   │   ├── fonts/
│   │   ├── img/
│   │   └── js/
│   └── templates/
├── tests/
├── .env.example
├── requirements.txt
├── migrate_db.py
├── migrate_sequence.py
├── migrate_v3.py
└── sicday.db
```

## How It Works

### Registration flow

1. A student searches for themselves from the imported roster.
2. The frontend submits `/api/register` with:
   - student identity
   - activity ID
   - optional team name
   - optional partner numbers
   - optional email
3. The backend validates:
   - activity is open
   - schedule window is valid
   - classroom restrictions
   - group quota rules
   - duplicate registration
   - team size and partner existence
4. If seats remain, the registration is stored with `status="registered"`.
5. If the activity is full, the registration is stored with `status="waitlisted"`, and an email is required.
6. When configured, the system sends:
   - a waitlist confirmation email immediately
   - a second email if that waitlisted record is later promoted to `registered`

### Waitlist promotion flow

Promotion currently happens in two places:

- when a student cancels their own registration
- when an admin removes a registered student from an activity

In both cases the oldest `waitlisted` record for that activity is promoted automatically. If the promoted record has a stored `contact_email` and SMTP is configured, the app sends a seat-granted email.

### Real-time updates

The app uses a WebSocket endpoint at `/ws/activities`. The backend broadcasts:

- `update_activities`
- `update_announcements`

The public page and admin dashboard reconnect automatically and reload their data when those messages are received.

## Quick Start

### Prerequisites

- Python 3.10+ recommended
- pip

### 1. Clone the repository

```bash
git clone https://github.com/Nonx2360/DSNPRU_REG.git
cd DSNPRU_REG
```

### 2. Create and activate a virtual environment

```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the app

```bash
uvicorn backend.main:app --reload
```

### 5. Open the app

- Public home page: `http://127.0.0.1:8000/`
- Admin login: `http://127.0.0.1:8000/admin/login`
- API docs: `http://127.0.0.1:8000/docs`

## Configuration

The app can run with no environment variables for basic local usage.

### Default admin account

If the `admins` table is empty, the app seeds:

- username: `admin`
- password: `admin123`

Change this immediately after first login.

### Database

- default database file: `sicday.db`
- engine: SQLite via SQLAlchemy
- file is created automatically if it does not exist

### Mail configuration

Waitlist emails use SMTP settings stored in the project root `.env` file. You can either:

- create `.env` manually
- or configure values from the admin mail settings page at `/admin/settings`

Use this format:

```env
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_FROM=your-email@gmail.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_FROM_NAME=DSNPRU Waitlist
```

The app also ships with [.env.example](.env.example).

### Gmail note

If you use Gmail, use an App Password, not your normal mailbox password.

## Waitlist Email Flow

### When a user joins the waitlist

If an activity is full:

- the registration is stored as `waitlisted`
- the frontend requires an email
- the backend stores that email in `registrations.contact_email`
- the app sends a waitlist confirmation email if mail settings are complete

### When a user gets a seat

If a registered student leaves an activity and a waitlisted student is promoted:

- the promoted registration changes from `waitlisted` to `registered`
- the app sends a promotion email if that registration has `contact_email`

### Where mail settings are managed

Admins can open `/admin/settings` to:

- set SMTP username, password, sender, port, and server
- view whether a password is already stored
- preview the `.env` format
- save changes directly to `.env`

No restart is required after saving mail settings through the admin UI because the running process updates its environment values immediately.

## Admin Guide

### Main admin pages

- `/admin/login`
- `/admin/dashboard`
- `/admin/activities`
- `/admin/activity/{activity_id}`
- `/admin/students`
- `/admin/announcements`
- `/admin/analytics`
- `/admin/platform/status`
- `/admin/export`
- `/admin/users`
- `/admin/logs`
- `/admin/settings`

### Typical admin workflow

1. Log in.
2. Import students from Excel.
3. Create activity groups if needed.
4. Create activities and set quotas, type, schedule, and restrictions.
5. Monitor registrations from the dashboard and activity detail pages.
6. Use announcements for public messaging.
7. Configure mail settings if you want waitlist email delivery.
8. Export registrations or student lists when needed.

### Student import format

The current import endpoint accepts `.xlsx` and `.xls` filenames and expects rows similar to:

- `รหัส`, `คำนำหน้า`, `ชื่อ`, `นามสกุล`, `ห้อง`, `เลขที่`

Rows are normalized into:

- `number`
- `name`
- `classroom`
- `sequence`

Existing students are updated by `number`.

### Activity behavior

Each activity supports:

- `title`
- `description`
- `max_people`
- `status` (`open` or `close`)
- `allowed_classrooms`
- `start_time`
- `end_time`
- `color`
- `group_id`
- `type` (`individual` or `team`)
- `max_team_size`

### Activity groups

Groups support:

- group name
- quota per student
- allowed classrooms
- visibility toggle

Public activity listing only shows activities that are:

- `status == "open"`
- in a visible group, or ungrouped

### Announcements

Announcements support:

- message text
- active / inactive status
- urgent / non-urgent mode
- color choice

Behavior:

- non-urgent announcements show as top banners
- urgent announcements show as SweetAlert modals
- announcement changes are broadcast in real time

### Platform monitoring

The admin platform endpoints expose:

- API health
- DB health
- DB file size
- uptime percentage approximation
- request counts
- average response time
- error rate
- grouped trends over time

## Student Guide

### Registering

1. Open the home page.
2. Search for your name or student number.
3. Select an activity.
4. If it is a team activity, optionally:
   - give the team a name
   - add partner students
   - choose to apply alone
5. If the activity is full, enter an email for waitlist confirmation.
6. Submit the registration.

### Checking registrations

Use the "ตรวจสอบข้อมูล / ยกเลิก" tab on the home page and enter the student number to load current registrations.

### Canceling

Students can cancel their own registration while the activity is still open. If they cancel a registered seat, the next waitlisted student is promoted automatically.

## Routes

### Page routes

#### Public pages

- `GET /`
- `GET /activities`
- `GET /about`

#### Admin pages

- `GET /admin/login`
- `GET /admin/dashboard`
- `GET /admin/activities`
- `GET /admin/activity/{activity_id}`
- `GET /admin/export`
- `GET /admin/students`
- `GET /admin/settings`
- `GET /admin/logs`
- `GET /admin/users`
- `GET /admin/analytics`
- `GET /admin/announcements`
- `GET /admin/platform/status`

### Public API

- `GET /api/search_students`
- `GET /api/announcements/active`
- `GET /api/activities`
- `POST /api/register`
- `GET /api/my_registrations`
- `POST /api/cancel_registration`
- `GET /api/system_info`

#### `POST /api/register` request body

```json
{
  "name": "Student Name",
  "classroom": "ม.6/1",
  "number": "64001",
  "activity_id": 1,
  "email": "student@example.com",
  "team_name": "Alpha Team",
  "partner_numbers": ["64002", "64003"]
}
```

Notes:

- `email` is optional for normal registrations
- `email` is required when the selected activity is full and the registration will be waitlisted
- `partner_numbers` is used only for team activities

### Admin API

#### Authentication

- `POST /admin/login`
- `POST /admin/logout`
- `PUT /admin/change-password`

#### Dashboard and settings

- `GET /admin/api/dashboard`
- `GET /admin/api/settings/mail`
- `PUT /admin/api/settings/mail`

#### Admin user management

- `GET /admin/api/admins`
- `POST /admin/api/admins`
- `DELETE /admin/api/admins/{admin_id}`

#### Activity groups

- `POST /admin/api/activity_groups`
- `GET /admin/api/activity_groups`
- `PUT /admin/api/activity_groups/{group_id}`
- `DELETE /admin/api/activity_groups/{group_id}`

#### Activities and registrations

- `POST /admin/create_activity`
- `GET /admin/api/activities`
- `PUT /admin/activities/{activity_id}`
- `POST /admin/activities/{activity_id}/toggle`
- `DELETE /admin/activities/{activity_id}`
- `GET /admin/registrations/{activity_id}`
- `DELETE /admin/registrations/{reg_id}`
- `GET /admin/search_students`

#### Students

- `POST /admin/api/import_students`
- `GET /admin/api/students`
- `PUT /admin/api/students/{student_id}`
- `DELETE /admin/api/students/{student_id}`
- `POST /admin/api/students/bulk-delete`
- `POST /admin/api/students/bulk-update-class`
- `GET /admin/api/classrooms`

#### Announcements

- `GET /admin/api/announcements`
- `POST /admin/api/announcements`
- `PUT /admin/api/announcements/{ann_id}`
- `DELETE /admin/api/announcements/{ann_id}`

#### Logs and analytics

- `GET /admin/api/logs`
- `GET /admin/api/analytics`
- `GET /admin/api/platform/status`
- `GET /admin/api/platform/metrics`
- `GET /admin/api/platform/export`

### Export API

- `GET /export/excel`
- `GET /export/pdf`
- `GET /export/students/excel`
- `GET /export/students/pdf`

`/export/excel` and `/export/pdf` accept optional `activity_id`.

### WebSocket

- `WS /ws/activities`

Broadcast messages used by the frontend:

- `update_activities`
- `update_announcements`

## Database Schema

### `students`

- `id` integer primary key
- `number` unique student number
- `name` student full name
- `classroom` optional classroom string
- `sequence` optional classroom sequence number

### `activity_groups`

- `id` integer primary key
- `name` unique group name
- `quota` maximum selections per student within the group
- `allowed_classrooms` comma-separated classroom restriction string
- `is_visible` visibility toggle for public listing

### `activities`

- `id` integer primary key
- `title`
- `description`
- `max_people`
- `status`
- `allowed_classrooms`
- `start_time`
- `end_time`
- `color`
- `type`
- `max_team_size`
- `group_id`

### `registrations`

- `id` integer primary key
- `student_id` foreign key to `students`
- `activity_id` foreign key to `activities`
- `team_name` optional team name
- `contact_email` optional waitlist email
- `status` registration state: `registered` or `waitlisted`
- `timestamp`

Constraint:

- unique `(student_id, activity_id)`

### `admins`

- `id`
- `username`
- `password_hash`
- `is_superuser`

### `admin_logs`

- `id`
- `admin_username`
- `action`
- `details`
- `ip_address`
- `timestamp`

### `announcements`

- `id`
- `message`
- `is_active`
- `is_urgent`
- `color`
- `timestamp`

### `request_logs`

- `id`
- `timestamp`
- `method`
- `path`
- `status_code`
- `response_time_ms`

### `system_metrics`

- `id`
- `timestamp`
- `metric_type`
- `value`
- `status`

## Exports

### Registration exports

Routes:

- `/export/excel`
- `/export/pdf`

Behavior:

- optional filtering by `activity_id`
- team activities include `team_name`
- records are sorted for easier reading

### Student exports

Routes:

- `/export/students/excel`
- `/export/students/pdf`

Behavior:

- exports all students ordered by classroom and sequence
- PDF export uses the bundled ChakraPetch font when available

## Runtime Schema Upgrades

The app does more than `Base.metadata.create_all(...)`.

At startup it also checks older databases and patches missing columns when needed. Current runtime fixes include:

- `registrations.contact_email`
- `announcements.is_urgent`

This is handled in [backend/main.py](backend/main.py).

Legacy migration scripts still exist for older installs:

- `migrate_db.py`
- `migrate_sequence.py`
- `migrate_v3.py`
- `add_col.py`

For a fresh install, you normally do not need them.

## Testing

The repository includes HTTP-level tests in `tests/`, including:

- authentication and security checks
- admin RBAC checks
- public functionality checks
- not-found and auth behavior

Typical usage depends on your local server setup. The tests use environment variables such as:

- `BASE_URL`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

If you want to run the live-server tests:

```bash
uvicorn backend.main:app --reload
```

Then in another terminal:

```bash
pytest
```

## Troubleshooting

### `no such column` SQLite errors

If you pull new code over an old database and see errors like:

- `no such column: announcements.is_urgent`
- `no such column: registrations.contact_email`

restart the app once so the runtime schema patcher in `backend/main.py` can run. If the DB is heavily customized, back it up before retrying.

### Waitlist emails are not sending

Check:

1. mail settings are saved in `.env`
2. all required mail fields are populated
3. the promoted or waitlisted registration has `contact_email`
4. your SMTP credentials are valid
5. Gmail uses an App Password if applicable

### Student cannot cancel

Current logic blocks self-cancellation when `activity.status == "close"`. That is expected behavior.

### Team registration is not appearing

Check:

- the activity `type` is `team`
- `max_team_size` is greater than `1`
- selected partner numbers exist in the student table

### Admin login does not work

Check:

- default account was not removed
- username/password are correct
- the browser still has a valid token flow

If needed for local development, back up and delete `sicday.db`, then restart to reseed the default admin.

## Security Notes

- the default seeded admin credentials are only for first-run convenience
- `SECRET_KEY` in `backend/auth.py` is still hardcoded and should be replaced for production use
- CORS is currently open to `*`
- SQLite is suitable for local or small deployments, but not ideal for high-write, high-concurrency production workloads
- mail credentials are stored in plaintext `.env`, so protect file access accordingly

## License

This repository is licensed under the [MIT License](LICENSE).
