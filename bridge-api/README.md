# zfc-bridge-api

HTTPS bridge for mobile and browser clients.

It keeps credentials, TLS, and UI-facing session access outside Zenoh while still using Zenoh as the control-plane transport.

## What it does

- login with username and password
- serve the browser console from the same HTTPS origin
- issue short-lived bearer tokens
- expose device/session state as HTTP JSON
- expose cached session events/results for mobile polling
- publish commands and controls into Zenoh
- query directory listings from the agent through Zenoh

## Local run

```bash
cd bridge-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
zfc-bridge-api
```

If you want to run the regression test, install `pytest` or use `python -m unittest`.

## TLS

Run it behind HTTPS with a server certificate and key:

```bash
zfc-bridge-api --host 0.0.0.0 --port 8443 \
  --ssl-certfile /path/to/server.crt \
  --ssl-keyfile /path/to/server.key
```

For Android and browsers, import the issuing CA certificate manually when using a private CA.
On Android debug builds, the app trusts user-installed CA certificates through `network_security_config`.
The debug Android app also contains an emulator-only trust bypass for `https://10.0.2.2`; release builds and real phones must use a trusted certificate.

## Authentication

Set login users as JSON:

```bash
export ZFC_BRIDGE_USERS='{"eame":"password"}'
```

Then call:

```bash
curl -k https://127.0.0.1:8443/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"eame","password":"password"}'
```

The Android app can then use the returned bearer token against the same bridge base URL.

The current username/password map is for local validation. Production should replace it with a hashed account store, rate limiting, audit logs, and token revocation.

## Browser console

Open the bridge root URL in a browser after starting `zfc-bridge-api`:

```text
https://127.0.0.1:8443/
```

Because the console is served by the bridge itself, the browser uses same-origin
HTTPS requests and does not need direct Zenoh access.

Use plain HTTP only for loopback-only automated tests. Real browser use should import the private CA or use a publicly trusted HTTPS certificate.

## Session events

Poll a session event snapshot after login:

```text
GET /v1/sessions/{username}/{device_id}/{session_id}/events?after_seq=0
Authorization: Bearer <token>
```

The response contains `items` for events and `results` for completed command results. The mobile
client can persist the last event sequence and send it as `after_seq` after reconnecting.

## Zenoh

The bridge subscribes to `u/<username>/fleet/*` status topics and publishes command/control messages back to Zenoh.
