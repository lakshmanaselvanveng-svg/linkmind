# LinkMind – Google Chat + Gemini prototype

A minimal HTTP Google Chat app that previews configured HTTPS links with a LinkMind card. Clicking **Summarize article** fetches the public webpage, extracts readable text, calls Gemini, and updates the original link-preview card.

## Important Google Chat constraints

- Google Chat native link previews require URL patterns registered in the Chat API configuration.
- A Chat app supports up to **five URL patterns**; it cannot automatically preview every arbitrary domain on the internet.
- Chat previews HTTPS links and previews only one matching link per message.
- The app must be added to the relevant Chat space.
- The card is attached alongside the link; Google Chat controls exact placement.
- The first prototype performs extraction and Gemini generation during the button-click request. Keep it short; for production, use a job queue and post a follow-up message or another supported interaction pattern rather than relying on a long synchronous request.

See Google's docs: https://developers.google.com/workspace/chat/preview-links

## Requirements

- Python 3.11+
- Google Cloud project with billing enabled for Cloud Run deployment
- Google Chat enabled for a Google Workspace account
- Gemini API key from Google AI Studio

## Local setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `GEMINI_API_KEY`. For local endpoint tests, keep `CHAT_AUTH_MODE=disabled`. This is development-only; do not deploy with authentication disabled.

Start the server:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

Run unit tests:

```powershell
pytest -q
```

## Local webhook smoke test

This tests the preview response shape only; it does not connect to Google Chat:

```powershell
$body = @{
  type = "MESSAGE"
  message = @{
    matchedUrl = @{ url = "https://example.com" }
  }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/chat/events -ContentType "application/json" -Body $body
```

Simulate a button click (the article fetch and Gemini call will run, so use a public article URL and a valid key):

```powershell
$body = @{
  type = "CARD_CLICKED"
  action = @{
    actionMethodName = "summarize"
    parameters = @(@{ key = "url"; value = "https://example.com" })
  }
  message = @{ sender = @{ type = "HUMAN" } }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/chat/events -ContentType "application/json" -Body $body
```

## Google Cloud deployment

Set variables (replace values):

```powershell
$PROJECT_ID = "YOUR_GCP_PROJECT_ID"
$REGION = "asia-south1"
$SERVICE = "linkmind-chat"
$RUNTIME_SA = "linkmind-runtime@$PROJECT_ID.iam.gserviceaccount.com"

gcloud auth login
gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com chat.googleapis.com
```

Create a runtime service account:

```powershell
gcloud iam service-accounts create linkmind-runtime --display-name="LinkMind Cloud Run runtime"
```

Create the Secret Manager secret before deployment. Keep the key out of source control and don't paste it into chat:

```powershell
$GEMINI_KEY = "PASTE_KEY_IN_YOUR_LOCAL_TERMINAL_ONLY"
$GEMINI_KEY | gcloud secrets create linkmind-gemini-key --data-file=-
```

If the secret already exists, add a version instead:

```powershell
$GEMINI_KEY | gcloud secrets versions add linkmind-gemini-key --data-file=-
```

Grant the runtime service account access to the secret:

```powershell
gcloud secrets add-iam-policy-binding linkmind-gemini-key `
  --member "serviceAccount:$RUNTIME_SA" `
  --role roles/secretmanager.secretAccessor
```

Deploy the service. Cloud Run allows the HTTPS request to reach the app, and FastAPI verifies Google's signed ID token before processing it:

```powershell
gcloud run deploy $SERVICE `
  --source . `
  --region $REGION `
  --service-account $RUNTIME_SA `
  --allow-unauthenticated `
  --set-env-vars "CHAT_AUTH_MODE=id_token,GEMINI_MODEL=gemini-3.8-flash" `
  --set-secrets "GEMINI_API_KEY=linkmind-gemini-key:latest"
```

After deployment, get the service URL and configure the exact endpoint URL as the Chat app's Authentication Audience:

```powershell
$SERVICE_URL = gcloud run services describe $SERVICE --region $REGION --format="value(status.url)"
$ENDPOINT = "$SERVICE_URL/chat/events"

gcloud run services update $SERVICE `
  --region $REGION `
  --update-env-vars "CHAT_AUTH_AUDIENCE=$ENDPOINT"

Write-Output $ENDPOINT
```

This prototype allows the HTTPS request to reach Cloud Run, then verifies Google's signed ID token inside FastAPI. The app checks both the exact audience and the Google Chat issuer email before processing an event. Do not set `CHAT_AUTH_MODE=disabled` in Cloud Run. For stricter perimeter protection, you can later configure Cloud Run IAM/custom audiences after validating the exact audience behavior for your deployment.

Google's Chat request verification guide: https://developers.google.com/workspace/chat/verify-requests-from-chat

## Configure Google Chat API

1. In Google Cloud Console, select the same project.
2. Open **APIs & Services → Library**, enable **Google Chat API**.
3. Open **Google Chat API → Configuration**.
4. Set the app name to `LinkMind`, description to `AI summaries for shared links`, and provide an HTTPS avatar URL if available.
5. Under **Connection settings**, choose **HTTP endpoint URL** and set it to `$ENDPOINT`.
6. Set **Authentication audience** to **HTTP endpoint URL** and use the exact same endpoint URL.
7. Enable **Interactive features** and configure the app to receive messages and card clicks.
8. Under **Link previews**, add URL patterns for domains you control or want to test. Example: host `example.com`, path prefix blank. Add no more than five patterns.
9. Save the configuration.
10. Add LinkMind to a test Chat space. Share an HTTPS link matching one of the registered patterns.

Google Chat link preview guide: https://developers.google.com/workspace/chat/preview-links

## Security notes before production

- `CHAT_AUTH_MODE=disabled` is only for local tests. In Cloud Run, use IAM invoker restriction and `CHAT_AUTH_MODE=id_token`.
- The app verifies the Google-signed ID token audience and `chat@system.gserviceaccount.com` issuer email.
- The extractor rejects non-public IPs and revalidates redirect targets. SSRF defenses should be strengthened further for production (e.g. egress firewall/proxy, DNS rebinding-resistant resolver, strict content-type/size controls).
- Never log API keys, bearer tokens, or full private message contents.
- The webpage is untrusted input; the summarization prompt explicitly treats it as source material, not instructions.
- Respect website terms, robots policies, copyright, paywalls, and access controls. Do not attempt to bypass authentication.
- The current prototype returns the summary in the card-click response. If generation regularly exceeds Chat's interaction response window, move processing to Cloud Tasks/Pub/Sub and send a separate follow-up message using the Chat API.

## Project layout

```text
linkmind-google-chat-prototype/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── security.py
│   ├── cards.py
│   └── services/
│       ├── extractor.py
│       └── summarizer.py
├── tests/
│   └── test_cards.py
├── .env.example
├── Dockerfile
├── requirements.txt
└── README.md
```
