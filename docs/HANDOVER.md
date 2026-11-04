# OHE Visual AI Patrol — Beta handover

This Beta is built to the "OHE Visual AI Patrol Application — Research HLD" v1.0.
- **Patrol staff** photograph the OHE with the phone app.
- **The server** inspects each photo and builds the cycle report.
- **An SSE, ADEE, DEE or Sr DEE** reviews and signs the report in a web browser.

There is no per-asset confirmation by patrol staff.

## What is in a release

Each GitHub pre-release (`beta-…`) contains:

| File | What it is |
|---|---|
| `RVI-OHE-Patrol-debug.apk` | Android app (Android 8 or later) |
| `docker-compose.yml`, `.env.example` | Server set-up |
| `add_user.sh` | Adds a user with a PIN |
| `demo.py` | End-to-end check with your own photos |
| `ohe_detector.onnx`, `ohe_detector.names.json` | The trained detector. It is already inside the server image; these copies are for audit. |

Server image: `ghcr.io/dhruvv2112-coder/rvi-ohe-server:latest` (private; run `docker login ghcr.io` with a GitHub token that has `read:packages`). To build it yourself instead, run `docker compose build` from `deploy/`.

## 1. Start the server (any Linux machine with Docker)

```
mkdir rvi && cd rvi        # put docker-compose.yml, .env.example and add_user.sh here
cp .env.example .env       # set RVI_SECRET_KEY to a long random value
docker compose up -d
curl http://localhost:8000/health
```

`/health` should show `"ohe_detector":"onnx:ohe_detector.onnx"` and `"ohe_ocr":"rapidocr-ppocr-zero-shot"`.

Everything the server keeps (database, original photos, users) is in `./data`. Back up that folder.

Put the server behind HTTPS (for example, the division's reverse proxy) before phones use it over the internet.

## 2. Add users

```
./add_user.sh PT-0412  Patrol 4826 "Patroller, Jaipur"
./add_user.sh SSE-1205 SSE    7391 "SSE TRD Jaipur"
```

| Role | What it can do |
|---|---|
| `Patrol` | Captures photos |
| `SSE`, `ADEE`, `DEE`, `SrDEE` | Reviews and signs reports |
| `Admin` | Reserved |

PINs are stored only as salted hashes. Re-running the command for the same ID replaces that user.

## 3. Phone app

1. Install the APK. Allow camera, microphone and location.
2. On the home screen, enter:
   - **Your ID** and **PIN**, then tap **Sign in**.
   - **Server address**, for example `https://rvi.example.in/`.
   - **Section**.
3. Tap **Start patrol**. Photograph each mast, insulator and fitting from where you stand.
   - Photos are kept on the phone and upload by themselves when there is a network.
   - If the server or the phone's own check asks for a retake (blur, too small, number plate), the request appears on screen and is spoken. No request ever asks you to move closer to the OHE.
   - Voice commands, in English or Hindi: "photo", "note …", "end patrol".
   - Notes go to the reviewer and are never used by the inspection.
4. Tap **End patrol**. Once every photo has uploaded, the report is created, and the end screen shows its summary.

Urgent findings are raised the moment their photo is uploaded. They don't wait for the report. Set `RVI_ALERT_WEBHOOK` to forward them to an SMS or chat gateway.

## 4. Review and sign

Open `http://<server>:8000/ohe/review` and sign in with a reviewer ID and PIN.

- **Urgent findings:** the live feed.
- **Patrol reports:** newest first. A report shows:
  - the summary (count definitions are listed in the report);
  - items needing a reviewer decision: mast not identified, unfamiliar appearance, not assessable, no photo, unsupported design;
  - each finding with photos and the detected boxes;
  - the three-part claim: observed, hypothesis, action;
  - the rule and authority, routing, and scores (marked uncalibrated).
- **Amend:** set the mast, priority or state, with a reason. This creates a new revision; earlier revisions are kept.
- **Sign:** freezes that revision (its SHA-256 is recorded). Any later change becomes a new revision.
- **Print view:** prints the frozen revision, or saves it as PDF from the browser.

## 5. Check the whole chain

```
python3 demo.py --server https://rvi.example.in --id PT-0412 --pin 4826 photos/*.jpg
```

## What this Beta can and cannot claim

- **Trained classes:**
  - insulator and insulator damage
  - bird nest and foreign objects (kites, bags, balloons)
  - vegetation
  - mast (pole)
  - corrosion

  They were trained on public data: drone views of transmission lines, Indian 11 kV distribution poles photographed from the ground, and partly synthetic railway foreign-object images. None of it is ground-level 25 kV railway OHE.
- **Accuracy on Railway photos is not yet known.** Per-class results on public test data are in `docs/OHE_SOLUTION_DEFINITION.md` §7.
- **Only these give findings:**
  - insulator damage
  - nests and foreign objects

  Masts, corrosion and vegetation are detected but reported as "unsupported" until they are validated on Railway photos.
- **No model yet for:** droppers, contact wire, mast number plates as objects, and cantilever fittings. They need pilot photos.
- **Mast identity** is accepted only when the number plate is read and agrees with the location corridor; otherwise the finding keeps its candidate masts. Plate reading is zero-shot until it is fine-tuned on Railway plates.
- **The unknown-defect (anomaly) check is weak:** AUROC 0.61–0.63, and it did not transfer to railway cantilever parts. It only sends photos to review.
- **Not part of this Beta:** comparison with earlier cycles, an AI-written narrative, and calibrated confidence.

## After handover

1. Pilot photo capture on one section.
2. Label those photos.
3. Retrain, and fine-tune plate reading.
4. Per-class validation and acceptance thresholds, then calibration.
5. Hindi terminology review.
6. Production hosting and integration.
7. Field trial, then go / no-go.

See `docs/OHE_Patrol_Project_Plan.xlsx`.


## Draft 1: laptop server + phone app (5 Nov 2026)

Release **draft-1** (GitHub pre-release) holds `OnTrack-Server-Windows.zip` and `OnTrack.AI.apk` (0.3.3004-draft).

1. On the Windows laptop: unzip, double-click `Start-OnTrack.bat`. First run installs Python 3.11 and the server
   (3-6 min), asks for a patroller and an SSE account, asks Windows once to allow port 8000 on private networks,
   and adds a desktop shortcut. Data lives in `%LOCALAPPDATA%\OnTrack`.
2. The connect page opens (`http://localhost:8000/ohe/connect`): scan the first QR code with the phone to install the app.
3. The app finds the laptop on the same Wi-Fi by itself (mDNS `_ontrack._tcp`); otherwise type the address shown.
4. Reviewer page on the laptop: `http://localhost:8000/ohe/review`.

The Windows package is smoke-tested on every draft build (CI workflow `draft`): first-run install, sign-in, photo
upload, end of patrol and app download. Draft APKs are signed with the CI debug key: when the Beta signing key is
added to CI secrets, uninstall the draft once before installing a signed Beta.


### Using the phone away from the laptop (draft 1, internet layer)

- The laptop opens an outbound Cloudflare quick tunnel (no account, no router changes) and shows its HTTPS address
  on the connect page. Start with `-LanOnly` to switch this off, or `-PublicUrl https://...` for a fixed address
  (named Cloudflare tunnel or ngrok static domain).
- The quick-tunnel address changes on every restart. The server posts its current address to a private ntfy.sh
  topic, signed with HMAC-SHA256 using a key only paired phones get (GET /ohe/connect/pairing after sign-in).
  A phone that cannot reach the laptop reads the newest signed address, checks it and switches.
- Pair each phone once: sign in on the laptop's Wi-Fi, or type the HTTPS address from the connect page.
- Internet-facing hardening: 5 wrong PINs lock the ID and the caller (1, 2, 4 ... 60 min); connect page and
  server info are hidden through the tunnel; API docs are off; tokens travel only over HTTPS on the internet path.
- Verified on every draft build on a Windows runner: tunnel address, health, sign-in, pairing, hidden pages,
  lockout (429) and a correctly signed relay message, all through the public internet.
