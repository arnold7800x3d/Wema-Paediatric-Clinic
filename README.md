# Wema Paediatric Clinic - Booking API

A REST API for a small clinic (5 doctors) to manage patient appointment bookings, built with FastAPI and PostgreSQL.

## Live links

- **Deployed API:** https://wema-paediatric-clinic.onrender.com
- **Interactive docs (Swagger UI):** https://wema-paediatric-clinic.onrender.com/docs
- **Repository:** *https://github.com/arnold7800x3d/Wema-Paediatric-Clinic.git*

> Note: the application is hosted on Render's free tier, which spins down after about 15 minutes of inactivity. The first request after a period of inactivity may take about 30 to 60 seconds to respond while the instance wakes up.

---

## 1. System Design

### Models and Key Components

- **Doctor** — `doctorid` (manually assigned, e.g. `DR-0001`), name, email, shift start/end (`time without timezone`, no date). Fixed at 5 rows to represent the five doctors and manually entered in the database with no endpoints to create or update doctor's information.
- **Patient** — `patientid` (auto-incrementing), name, email. Minimal with no authentication and patient data was also manually entered with no endpoints to create or update their information in the database.
- **Appointment** — the core entity of the REST API. `appointmentid` (auto-increment), `doctorid` and `patientid` (foreign keys), `appointmentdate`, `starttime`, `status` (`booked` / `cancelled` — a Postgres enum), and `cancellationreason` (nullable, only populated on cancel/reschedule).

### Key decisions

**How I defined a "slot":** Fixed grid, not flexible. A doctor's shift (e.g. 08:00–10:00) is deterministically divided into 30-minute increments using a custom function (`generateSlots(shiftStart, shiftEnd)`), producing a fixed set of valid start times. It takes the shift times of a doctor as defined in the database and is able to get the slot times for each doctor. The doctors work in shifts where each doctor's shift is only 2 hours, meaning each one can only have a maximum of 4 slots in their shifts. A booking request is only valid if its `starttime` exactly matches one of these generated slot boundaries as there's no support for arbitrary or partial-length appointments. This was a deliberate simplification: it makes availability checking a simple set-difference operation (all slots minus booked slots) rather than an interval-overlap problem, which is significantly simpler to reason about and test correctly given the time constraint of the technical assessment. The trade-off is inflexibility where a real clinic might want variable-length appointment types (15 min for a follow-up, 45 min for a new patient), which this model doesn't support.

**Concurrency safety (the "must not be available to others" requirement):** This is enforced at two levels, deliberately redundant:
1. **Application-level checks** in the route (working hours, not in the past/within 1 hour, doctor/patient exist). These exist purely for clean, specific error messages.
2. **Database-level enforcement** via a **partial unique index**: `UNIQUE (doctorid, appointmentdate, starttime) WHERE status = 'booked'`. This is the actual source of correctness. Two simultaneous requests for the same slot will both pass the application-level checks (since neither has committed yet), but only one `INSERT` will succeed at the database level as the second raises an `IntegrityError`, which the route catches and converts into a `409 Conflict`. The application checks alone are not sufficient to prevent double-booking under real concurrency; the index is what actually guarantees it.

**Why a partial index instead of a plain unique constraint:** A plain `UNIQUE(doctorid, appointmentdate, starttime)` would permanently block that slot combination the moment one row existed there, even after cancellation, because the constraint doesn't know about `status`. Cancelling an appointment needs to free the slot for rebooking. The partial index (`WHERE status = 'booked'`) only enforces uniqueness among currently-booked rows, so a cancelled row no longer counts, and the same slot can be booked again.

**Cancel = soft delete, not row deletion:** Cancelling flips `status` to `cancelled` and records a reason, rather than deleting the row. This preserves an audit trail (useful for the bonus "upcoming appointments" endpoint and for any future reporting) and is what makes the partial-index approach work at all.

**Reschedule = cancel-old + book-new, same transaction:** Rescheduling doesn't mutate the existing row's date/time in place. Instead, it flips the old row's status to `cancelled` (with an automatic system reason) and inserts a brand new row for the new slot, in a single commit. This reuses the exact same validation and conflict-handling logic as a fresh booking, rather than inventing a third code path.

### Trade-offs considered and deliberately not addressed (see reflection questions below for how I'd approach these)

- No timezone handling - all times are stored and compared as local time.
- No authentication/authorization - any caller can book, cancel, or reschedule on behalf of any `patientid`.
- No endpoint for a doctor cancelling an entire day's bookings in bulk.
- Doctor shift changes aren't validated against existing future bookings - changing a doctor's hours could silently orphan bookings outside the new hours.

Kindly see the reflection section for how I'd reason about each if extending this.

---

## 2. API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/doctors/` | List all doctors |
| GET | `/doctors/{id}/availability?on_date=YYYY-MM-DD` | Available 30-min slots for a doctor on a date |
| POST | `/appointments/` | Book a slot |
| PATCH | `/appointments/{id}/cancel` | Cancel a booking (requires a reason) |
| PATCH | `/appointments/{id}/reschedule` | Move a booking to a new slot |
| GET | `/appointments/patients/{id}/appointments` | Upcoming bookings for a patient, sorted by date |

Full interactive documentation, including request/response schemas, is available at `/docs`.

---

## 3. Running Locally

### Prerequisites
- Python 3.12+
- A PostgreSQL database (local or cloud — this project was developed against a cloud instance throughout, so a local Postgres install is not required)

### Setup

```bash
git clone https://github.com/arnold7800x3d/Wema-Paediatric-Clinic.git
cd wemaPaediatricClinic

python -m venv .venv
# This is to create a virtual environment. To activate it, see below:
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
DB_URL=postgresql+asyncpg://<user>:<password>@<host>/<dbname>
```

Run the schema setup SQL (see `schema.sql` in the repo) against your database to create the tables, enum type, and the partial unique index.

Run the app:

```bash
fastapi dev main.py
```

Visit `http://127.0.0.1:8000/docs`.

### Running tests

```bash
pytest -v
```

Tests run against the actual Postgres database (the one specified in `DB_URL`). Each test that writes data cleans up after itself.

---

## 4. CI/CD

**Pipeline file:** `.github/workflows/ci.yml`

**What it does:**
- **On every pull request into `main`:** runs the full `pytest` suite against the project's Postgres database (connection string supplied via the `DB_URL` GitHub Actions secret). If any test fails, the check fails and blocks the PR from being merged (via branch protection).
- **On every push to `main`** (i.e. when a PR is merged): after the `test` job succeeds, a `deploy` job fires, which sends a POST request to a Render **Deploy Hook** URL (stored as the `RENDER_DEPLOY_HOOK` secret). This tells Render to pull the latest `main` and redeploy. The deploy job explicitly depends on the test job (`needs: test`), so a failing test suite can never trigger a deploy.

**Designated branch:** `main`. Render's own Auto-Deploy setting is switched **off**, so the GitHub Actions webhook is the sole deploy trigger thus avoiding double-deploys from two independent mechanisms.

---

# Section 4: AI Reflection

**1. What did I use AI for across the four sections?**
- Talking through system design trade-offs before writing code (slot representation, cancel-as-status-flip vs. delete, why a partial unique index rather than a plain one).
- Debugging - reading tracebacks and narrowing down root causes (import errors, an `httpx`/`asyncpg`/Windows event-loop incompatibility in the test suite, a missing trailing comma in `__table_args__`).
- Learning FastAPI/SQLAlchemy/pytest concepts I hadn't used before (async sessions, dependency injection via `Depends`, generator-based cleanup with `yield`, pytest fixtures), asked in a "point me at the concept, let me write it" style rather than "just give me the code," for most of the build.
- Drafting this README structure.

**2. One example where an AI suggestion improved my work:**
I initially planned to represent doctor availability slots as labelled letters (slot "a", "b", "c", "d") and use them to represent the slot times rather than actual times. I prompted: *"each doctor's slots... assign letters to each slot... I want to reuse this for each doctor."* The AI pushed back and walked through why this adds a translation layer with no real benefit as every downstream operation (validating a booking, checking the unique constraint, displaying availability to a patient) would need to convert between letters and real times anyway, so it's pure overhead. I switched to using actual `time` objects as the slot representation throughout, which simplified the booking, availability, and uniqueness-checking logic considerably.

**3. One example where AI output was wrong or incomplete, and how I caught it:**
When I asked for a `cancellationreason` column, I initially set it as `NOT NULL` in my own SQL because "a reason is required" per the brief. This would have made every fresh booking fail to insert, since a booking has no cancellation reason yet as the requirement only applies at cancel-time, not at the schema level. I caught this myself by reasoning through what a freshly booked (not cancelled) row would need to contain, and flagged it before running the migration; the fix was making the column nullable and enforcing "reason required" as an application-level check inside the cancel route instead.

**4. Two decisions I made without AI, and why I trusted my own judgment:**
- **Enum vs. plain string for appointment status.** After being corrected on what Enum actually does (restricting valid values, not "setting defaults" as I initially assumed), I chose Enum myself, understanding the trade-off: slightly more setup cost, in exchange for the database itself rejecting invalid status values rather than relying on application discipline.
- **Cancel-and-rebook (two rows) vs. an in-place "rebooked" status for reschedules.** I was offered a third status option (`rebooked`) as a more descriptive alternative. I chose to reject it and stick with the simpler `cancelled` + reason string, because I recognized it would require touching every existing status check across the codebase to treat `rebooked` the same as `cancelled` in most places which meant extra surface area for bugs, for marginal descriptive benefit, that I judged wasn't worth the hustle considering the time constraint of the assessment.

---

## Notes for further discussion (known gaps, not yet implemented)

- **Timezone handling:** Currently naive local time throughout; no UTC normalization. This was because I imagined the clinic is doing physical bookings, and thus assumed it made sense that a patient would make a physical booking for a clinic which they were easily within reach and thus within the same time zone. For a real multi-location or remote-booking clinic, I'd store all `appointmentdate`/`starttime` values in UTC and convert to the clinic's local timezone only at the API boundary (request parsing and response formatting), to avoid ambiguity around daylight saving transitions and multi-timezone patients. 
- **Doctor shift changes vs. existing bookings:** Not currently validated. Changing a doctor's `doctorshiftstart`/`doctorshiftend` would not retroactively check or flag existing future bookings that might now fall outside the new hours. A real implementation would need either a blocking check (reject the shift change if it orphans bookings) or a reconciliation step (flag/notify affected bookings).
- **Authentication:** Not implemented. There is currently no check that a caller is authorized to book, cancel, or reschedule on behalf of a given `patientid` - any client can act as any patient. A real system would need patient authentication (at minimum, a token tied to a patient identity) and probably a separate staff/admin role for doctor-side operations.
- **Doctor cancelling an entire day:** Not implemented as a single operation. Currently this would require calling cancel on each individual appointment for that doctor/date. A dedicated endpoint could accept a doctor + date and a single reason, then bulk-update all matching `booked` rows to `cancelled` in one transaction.
- **Reschedule atomicity and the "slot taken mid-request" race:** The reschedule route cancels the old row and inserts the new row within a single database transaction/commit. If the new slot has been taken by another booking between the availability check and the commit, the `INSERT` fails the partial unique index, an `IntegrityError` is raised, and the **entire transaction rolls back**, including the cancellation of the original slot. This means the patient does not lose their original booking if the new slot turns out to be taken; the operation fails cleanly and atomically, and the client receives a `409` indicating the new slot is unavailable.
