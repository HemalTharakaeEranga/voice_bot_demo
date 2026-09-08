# Security notes

This repository is a clinic booking demonstration. It is not a production healthcare system
and has not been certified for regulated or real patient data.

## Threat model

The assets in scope are the optional server-side OpenAI key and quota, service availability,
the integrity of bundled voice models and demo appointment slots, and the small amount of booking
data stored in SQLite.
The main trust boundaries are the browser-to-FastAPI requests, FastAPI-to-OpenAI requests, and
FastAPI-to-SQLite operations.

Assume an internet client can send arbitrary HTTP methods, headers, bodies, UUIDs, booking text,
and concurrent requests. The application does not assume that a Host, Origin, session UUID, or
source IP proves a user's identity.

## Controls included

- The booking flow is a deterministic, task-limited state machine. User text is not executed as
  an LLM prompt and the bot does not provide general medical advice.
- Pydantic validates request types, supported locales, and field lengths. HTTP bodies default to
  a 64 KiB limit. The transcription route allows up to 11 MiB of multipart data so it can carry
  the separately enforced 10 MiB audio limit.
- Session identifiers are server-generated UUIDv4 values. Unknown UUIDs are rejected. Inactive
  sessions expire after 30 minutes, and the process retains at most 1,000 sessions using
  least-recently-used eviction. Completed responses remain replayable until their session expires.
- SQLAlchemy expression queries and ORM inserts bind user values as parameters. No request value
  is concatenated into SQL. A database unique constraint is the final protection against two
  writers booking the same date and time.
- Database integrity conflicts are mapped to a fixed 409 response. Other SQLAlchemy errors are
  rolled back and remain ordinary server errors; database exception details are not returned as
  appointment conflicts.
- Unsafe browser requests to /api/ are rejected when Origin does not match Host or Sec-Fetch-Site
  reports a non-same-origin context. Requests without browser origin headers remain available to
  command-line and server clients.
- Trusted-host validation rejects unexpected Host values. Configure ALLOWED_HOSTS for the exact
  production names. This prevents Host-header confusion; it is not authentication.
- The in-memory IP limiters have a configured request window, return Retry-After, ignore spoofable
  X-Forwarded-For, remove inactive buckets, and cap tracked clients at 4,096. Voice endpoints have
  a separate lower limit because cloud requests can consume paid quota and local synthesis uses
  significant CPU.
- API responses and the root document use `Cache-Control: no-store`; static assets must revalidate
  before reuse. Responses also receive a restrictive Content Security Policy, frame denial, MIME
  sniffing protection, a same-origin resource policy, referrer restrictions, and a microphone-only
  permissions policy.
- APP_ENV=production disables the OpenAPI schema and interactive documentation and enables an HSTS
  header. The production hostname must actually be served over HTTPS.
- The frontend renders untrusted conversation text with textContent. API output has a JSON content
  type. Tests cover SQL-injection-shaped values being stored literally, XSS-shaped JSON data,
  unknown sessions, host/origin rejection, body limits, method handling, and limiter bounds.
- There is no permissive CORS middleware, no API secret in browser code, and no transcript
  persistence. The .env file and local database files are excluded from Git.
- Local voice requests cannot select paths or models. Sinhala, Tamil, and Arabic use fixed files
  whose sizes and SHA-256 hashes are pinned, synthesis input is bounded, and sanitized errors hide
  model paths and runtime details. Per-voice locks and a two-job admission limit bound active CPU
  work.
- The container runs as a non-root user. CI runs Ruff, Bandit, dependency auditing, backend tests,
  and frontend tests.

## Important limits

The origin guard stops normal cross-site browser writes. It does not stop direct HTTP clients,
because such clients can omit browser-only headers. The trusted-host middleware and UUID session
identifier also do not authenticate a caller.

OpenAI-backed voice endpoints remain unauthenticated in this demo. The per-process limiter reduces
simple abuse but cannot reliably protect paid quota on a public deployment. Before exposing a
configured OpenAI key, place the application behind real user or demo-access authentication, a
shared API gateway rate limiter, provider budget alerts, and a hard spend limit.

Local synthesis is also unauthenticated and CPU intensive. Its admission limit prevents an
unbounded in-process synthesis queue, but public deployments still need authenticated access and a
shared gateway limit. Each application worker loads its own copy of each local model it uses.

The limiter and conversation store are local to one process. They reset on restart and are not
shared across workers. A reverse proxy may also make all requests appear to come from one address.
Only trust forwarded client addresses at a gateway configured with explicit trusted proxy
networks; this application deliberately does not parse X-Forwarded-For.

SQLite is suitable for this local demonstration, not a multi-user healthcare service. The demo
does not encrypt booking fields at the application layer, implement staff authorization, provide
audit trails, or define a real data-retention workflow. Use fake patient details only.

Automated tests and scanners cover known cases but do not prove the absence of vulnerabilities.

## Before a real deployment

1. Add authenticated access, role-based staff authorization, and an authorization review for every
   endpoint.
2. Replace SQLite with a managed database using encrypted storage, backups, restricted credentials,
   migrations, and audit logging.
3. Replace the process-local limiter and session store with shared infrastructure at a trusted
   gateway or service.
4. Use TLS, exact production hostnames, a secret manager, key rotation, and provider spend limits.
5. Define patient consent, retention, deletion, incident response, and backup-restoration
   procedures.
6. Complete the applicable privacy, healthcare, accessibility, and data-processing reviews.
7. Perform a formal threat model, dependency review, SAST, DAST, container and secret scans, and an
   independent penetration test.
