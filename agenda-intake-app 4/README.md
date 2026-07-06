# Agenda Intake App — Town of Sutton Clerk's Office

A small web app that lets multi-member bodies (boards, committees, commissions)
submit meeting agendas online instead of dropping off paper copies. It:

1. Accepts an uploaded Word (.doc/.docx) or PDF file through a web form.
2. Converts Word files to PDF automatically (PDFs pass through unchanged).
3. Stamps every page with "Received by Town of Sutton Clerk's Office" plus the
   date/time received, in U.S. Eastern time (displays as EST or EDT correctly
   depending on the time of year).
4. Emails the final, stamped PDF to the Clerk's office inbox
   (`agendas@town.sutton.ma.us`), ready to post.

The form can be used as a standalone page, or embedded directly into the town
website via `<iframe>`.

---

## 1. What your IT provider needs to do

The source lives in a GitHub repo; Railway builds and runs it directly from
that repo using the included `Dockerfile` — no separate server to manage.

**Steps:**

1. Push this project to a GitHub repository (see "GitHub setup" below — no
   git experience needed, there's a drag-and-drop option).
2. In Railway, create a new project from that GitHub repo (see "Deploying on
   Railway" below). Railway builds the Dockerfile and redeploys automatically
   on every push to `main`.
3. Generate a Railway domain (or point a custom subdomain, e.g.
   `agendas-intake.suttonma.gov`, at it) — Railway provides HTTPS
   automatically either way.
4. Set the environment variables described in `.env.example` in Railway's
   Variables tab — see the email setup section below for where the Resend
   credentials come from.
5. Confirm the Clerk's office receives a correctly stamped test email (see
   "Testing" below) before publicizing the form.

No database is required — nothing is stored after an email is sent
successfully.

---

## 2. GitHub setup

**Option A — upload through the GitHub website (no command line needed):**

1. On [github.com](https://github.com), click **New repository**, name it
   (e.g. `agenda-intake-app`), and create it **empty** — don't check "Add a
   README" or ".gitignore" (this project already has its own).
2. On the new, empty repo's page, click **uploading an existing file**.
3. Unzip the project folder on your computer, then drag everything inside
   `agenda-intake-app/` (the `app/` folder, `Dockerfile`, `README.md`, etc.)
   into the browser upload area, and commit.
4. **Important:** `.gitignore` and the `.github` folder are "dotfiles" that
   Finder (Mac) and File Explorer (Windows) hide by default. Turn on
   "show hidden files" before dragging, or those two items will be silently
   skipped — the app still works without them, but you'd lose the
   `.env`-protection and the automatic CI/image-build step.

**Option B — using git from the command line:**

```bash
cd agenda-intake-app
git init
git add .
git commit -m "Initial commit: agenda intake app"
git branch -M main
git remote add origin https://github.com/<your-org>/agenda-intake-app.git
git push -u origin main
```

Either way: `.env` should never be committed (Option B's `.gitignore` handles
this automatically; with Option A just don't upload your real `.env` file —
only `.env.example`). Real credentials go into Railway's environment
variables instead (see below).

---

## 3. Deploying on Railway

1. In Railway, click **New Project** → **Deploy from GitHub repo**, and
   select `agenda-intake-app` (authorize Railway's GitHub App if this is the
   first time connecting the two).
2. Railway detects the `Dockerfile` automatically and builds it — no extra
   config files needed. It also auto-redeploys on every push to `main`.
3. Open the service's **Variables** tab and add everything from
   `.env.example`: `RESEND_API_KEY`, `MAIL_FROM`, `AGENDAS_EMAIL`,
   `FLASK_SECRET_KEY`, `MAX_UPLOAD_MB`, `STAMP_TEXT`. Railway supplies its own
   `PORT` value automatically — the Dockerfile already reads it, so you don't
   need to set `PORT` yourself.
4. Under **Settings → Networking**, click **Generate Domain** for a free
   `*.up.railway.app` HTTPS URL, or add a custom domain (e.g.
   `agendas-intake.suttonma.gov`) by adding the CNAME record Railway shows you
   at your DNS provider.
5. Visit the generated URL to confirm the form loads before embedding it.

### Running it locally first (optional, recommended before deploying)

```bash
cd agenda-intake-app
cp .env.example .env
# edit .env with real values
docker build -t agenda-intake .
docker run -p 8080:8080 --env-file .env agenda-intake
```

Visit `http://localhost:8080` to see the form and confirm a test submission
works before pushing to Railway.

### Alternative: pulling the GitHub Actions-built image

The included `.github/workflows/build.yml` also publishes an image to
`ghcr.io/<your-org>/agenda-intake-app:latest` on every push to `main`. Railway
doesn't need this (it builds the Dockerfile itself), but it's there if you
ever want to run the same image on a different host without a build step:

```bash
docker pull ghcr.io/<your-org>/agenda-intake-app:latest
docker run -p 8080:8080 --env-file .env ghcr.io/<your-org>/agenda-intake-app:latest
```

---

## 4. Embedding on the town website

Once deployed, embed the form with an iframe pointed at the `/embed` route
(a version of the form without the page header, so it blends into the
surrounding page):

```html
<iframe
  src="https://agenda-intake-app.up.railway.app/embed"
  style="width: 100%; max-width: 600px; height: 720px; border: none;"
  title="Submit a Meeting Agenda">
</iframe>
```

Replace the `src` with your actual Railway-generated domain (or custom domain,
if you set one up in step 4 of "Deploying on Railway"). Adjust the `height` if
your board/committee name or file inputs wrap onto extra lines on smaller
screens.

---

## 5. Email setup (Resend)

The app sends email through [Resend](https://resend.com), authenticated with
an API key — no SMTP credentials needed.

**Setup:**

1. Create a Resend account at [resend.com](https://resend.com).
2. Under **Domains**, add and verify `suttonma.gov` (or a dedicated subdomain
   like `mail.suttonma.gov` if you'd rather keep it separate from the town's
   main mail flow). Verification adds a few DNS records (SPF, DKIM) at your
   DNS provider; propagation is usually quick but can take up to a day.
3. Under **API Keys**, create a key scoped to "Sending access" and copy it.
4. Set in `.env` / your platform's environment variables:
   - `RESEND_API_KEY=<the API key>`
   - `MAIL_FROM=Sutton Agenda Intake <agenda-intake@suttonma.gov>` (must be on
     the verified domain)
   - `AGENDAS_EMAIL=agendas@town.sutton.ma.us` (destination inbox is
     unchanged — still the town's existing Google Workspace group)
5. Make sure `agendas@town.sutton.ma.us` (a Google Group, per the original
   request) accepts mail from outside senders/domains — Workspace Groups
   sometimes restrict posting to members/domain only. Since mail will now
   arrive from `suttonma.gov` rather than the group's own domain, add that
   sending domain as an approved sender, or set the group's posting
   permission to allow external senders.

Resend's free tier is generally enough for a low-volume intake form like this
one; check [resend.com/pricing](https://resend.com/pricing) for current
limits. Submissions and delivery status can be reviewed anytime in the Resend
dashboard under **Emails**.

---

## 6. Testing before go-live

1. Deploy with real `.env` values pointed at a **test** recipient first (set
   `AGENDAS_EMAIL` to your own inbox temporarily).
2. Submit both a `.docx` and a `.pdf` test agenda through the form.
3. Confirm:
   - The received email has a PDF attachment (even when a Word doc was
     uploaded).
   - Every page shows the stamp box in the top-right corner with the correct
     date, time, and "EST"/"EDT" label.
   - The email subject and body show the board/committee name, submitter,
     and received time.
4. Switch `AGENDAS_EMAIL` back to `agendas@town.sutton.ma.us` and do one final
   live test with the Clerk's office watching for it.

---

## 7. Customizing

All of the following are environment variables (no code changes needed):

| Variable | Purpose |
|---|---|
| `STAMP_TEXT` | The text on the stamp, default "Received by Town of Sutton Clerk's Office" |
| `AGENDAS_EMAIL` | Destination inbox for the final PDF |
| `MAX_UPLOAD_MB` | Max upload size in MB (default 25) |

To change the stamp's position, size, or font, edit `app/stamper.py`
(`_make_stamp_overlay`). To add fields to the form (e.g., a meeting date
picker), edit `app/templates/index.html` and read the new field in
`app/app.py`'s `/submit` route.

---

## 8. File structure

```
agenda-intake-app/
├── .github/
│   └── workflows/
│       └── build.yml   # CI: compile check + Docker build/publish to ghcr.io
├── .gitignore
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md
└── app/
    ├── app.py          # Flask routes: form, submit handler, embed route
    ├── converter.py     # Word -> PDF conversion via LibreOffice headless
    ├── stamper.py        # Adds the "received" timestamp stamp to the PDF
    ├── mailer.py          # Sends the final PDF via Resend
    ├── templates/
    │   └── index.html     # Upload form (shared by / and /embed)
    └── static/
        └── style.css
```
