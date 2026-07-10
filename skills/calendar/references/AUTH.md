# Authentication — gmail & calendar skills

These two skills share **one** credential. You authorize **once** and both work.
The agent never authenticates; at runtime the skills only read a ready-made
credential from the `GOOGLE_CREDENTIALS_JSON` env var and silently refresh
access tokens.

There are two ways to populate `GOOGLE_CREDENTIALS_JSON`. Pick **A** for a
personal Google account (most people). Pick **B** only for Google Workspace with
admin access.

---

## A. Personal account — authorized-user credential (recommended)

You do a one-time browser consent on a machine that *has* a browser (e.g. your
laptop), then copy the resulting JSON to the home server. The JSON contains a
**refresh token**, so the server never needs a browser again.

### 1. Create a Google Cloud project + enable the APIs

1. Go to <https://console.cloud.google.com/> and create (or pick) a project.
2. **APIs & Services → Library** → enable **Gmail API** and **Google Calendar
   API**.

### 2. Configure the OAuth consent screen

1. **APIs & Services → OAuth consent screen**.
2. User type **External** (or Internal for Workspace). Fill in the app name and
   your email.
3. Add yourself under **Test users** (a test app issues refresh tokens that work
   indefinitely for test users; you don't need to publish).
4. You do *not* need to pre-add scopes here — the script requests them.

### 3. Create an OAuth client (Desktop app)

1. **APIs & Services → Credentials → Create credentials → OAuth client ID**.
2. Application type: **Desktop app**. Create.
3. **Download JSON** → save it as `client.json`. This is the *client* secret —
   it identifies the app, but on its own it cannot read your mail. It does NOT
   go in the env var.

### 4. Run the one-time consent (on a machine with a browser)

From either skill's directory:

```bash
pip install -r requirements.txt
python3 scripts/authorize.py --client client.json
```

A browser opens; sign in and approve Gmail + Calendar. On success the script
prints a single line of JSON like:

```json
{"type": "authorized_user", "client_id": "...", "client_secret": "...", "refresh_token": "...", ...}
```

**Browser on a different machine than the script** (e.g. you SSH into the box,
or the auto-opened browser/listener never connect)? Use the **manual paste
flow** — no local listener, works anywhere:

```bash
# 1. Print the auth URL and stage the flow state:
python3 scripts/authorize.py --client client.json --manual

# 2. Open that URL in ANY browser, approve. The browser then tries to load
#    http://localhost:8765/?code=... and shows "This site can't be reached" —
#    that is expected. Copy the FULL URL from the address bar.

# 3. Exchange the pasted URL (or the bare code= value) for the credential:
python3 scripts/authorize.py --manual-finish "http://localhost:8765/?...&code=4/0A..."
```

It prints the same `authorized_user` JSON. (`--no-browser` is an alternative
that keeps a local listener and only prints the URL — useful when you *can*
reach the script's `localhost`, e.g. via `ssh -L 8765:localhost:8765`.)

You can also pass the client secret inline instead of a file:

```bash
python3 scripts/authorize.py --client-json "$(cat client.json)"
```

### 5. Put the JSON in the env var on the home server

Copy the printed `{"type": "authorized_user", ...}` JSON and set it as
`GOOGLE_CREDENTIALS_JSON`. It is a secret — treat it like a password.

```bash
# e.g. in the service's environment / .env / systemd unit / docker-compose:
export GOOGLE_CREDENTIALS_JSON='{"type":"authorized_user","client_id":"...","client_secret":"...","refresh_token":"..."}'
```

The env var may hold the **inline JSON** (preferred) or a **path** to a JSON
file — the skills accept either.

### 6. Verify

```bash
python3 scripts/gmail.py profile          # from the gmail skill
python3 scripts/gcal.py calendars         # from the calendar skill
```

Both should return JSON with no prompt. Done.

---

## B. Google Workspace — service account with domain-wide delegation

Use this only if you administer a Workspace domain and want fully unattended
auth with no human consent step. (Service accounts **cannot** access consumer
`@gmail.com` mailboxes — personal accounts must use option A.)

1. Create a service account; create and download a **JSON key**.
2. In the Workspace **Admin console → Security → API controls → Domain-wide
   delegation**, authorize the service account's client ID for these scopes:
   `https://www.googleapis.com/auth/gmail.modify`,
   `https://www.googleapis.com/auth/calendar`.
3. Set `GOOGLE_CREDENTIALS_JSON` to the **service-account key JSON**
   (`{"type":"service_account", ...}`).
4. Set `GOOGLE_DELEGATED_SUBJECT` to the user to impersonate, e.g.
   `export GOOGLE_DELEGATED_SUBJECT=me@my-workspace-domain.com`.

The skills auto-detect the `service_account` type and impersonate that subject.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `GOOGLE_CREDENTIALS_JSON is not set` | Export the env var (option A step 5 / B step 3). |
| `holds raw OAuth *client* secrets` | You put `client.json` in the env var. The env var needs the **output of authorize.py**, not the client secret. |
| `Failed to obtain an access token … refresh token … revoked` | The refresh token expired/was revoked. In an agent run, use `python3 scripts/authorize.py --from-env --manual`, ask the user to open the URL and paste the final redirect URL, exchange it with `python3 scripts/authorize.py --manual-finish '<url>' > /tmp/google-credential.json`, then persist it with `python3 scripts/save_credentials.py --credential-file /tmp/google-credential.json`. Publishing the OAuth app, or leaving it in "Testing", both keep test-user tokens valid; deleting the test user revokes them. |
| `unrecognized shape` | The JSON isn't an `authorized_user` or `service_account` credential. Re-run `authorize.py`. |
| `access_denied` during consent | Add your email under **Test users** on the OAuth consent screen. |
