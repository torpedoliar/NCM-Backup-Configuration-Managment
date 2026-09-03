Using the API

The REST API exposes structured network documentation — per-switch identity, VLAN table and port configuration parsed from the latest successful backup — for external tools. Read-only, authenticated with API keys. Port 8443 is the default; use the port shown in the Service tab if changed.



Authentication

Send your API key as X-API-Key: <key> or Authorization: Bearer <key>. Keys are shown in full only once, at creation. If a key leaks, revoke it here and create a new one.



GET /api/v1/network-doc

Structured docs for all active switches (API key)

GET /api/v1/network-doc/{switch\_id}

Structured doc for one switch (API key)

POST /api/v1/api-keys

Create API key — plaintext returned once (admin JWT)

GET /api/v1/api-keys

List API keys (admin JWT)

DELETE /api/v1/api-keys/{id}

Revoke API key (admin JWT)

\# List structured docs for all active switches

curl -H "X-API-Key: <your-key>" \\

&#x20; http://localhost:8443/api/v1/network-doc



\# One switch by id (Bearer header works too)

curl -H "Authorization: Bearer <your-key>" \\

&#x20; http://localhost:8443/api/v1/network-doc/3

Each entry is built from the latest successful backup. Degraded output is reported in parse\_warnings (e.g. \["no successful backup"]) with an HTTP 200 — a bad backup never breaks the bulk response. Supported dialects: AlliedWare Plus CLI, Dell-style CLI, WebSmart SNMP dump (V1/V2).



{

&#x20; "switch\_id": 3,

&#x20; "name": "SW-CORE-01",

&#x20; "ip": "192.168.10.1",

&#x20; "protocol": "ssh",

&#x20; "hostname": "core01",

&#x20; "source\_backup\_id": 442,

&#x20; "backup\_taken\_at": "2026-08-18T04:00:00+00:00",

&#x20; "vlans": \[ { "id": 88, "name": "IPH-DEVICE" } ],

&#x20; "ports": \[ {

&#x20;   "name": "port1.0.1",

&#x20;   "description": "uplink",

&#x20;   "enabled": true,

&#x20;   "mode": "trunk",

&#x20;   "native\_vlan": 11,

&#x20;   "access\_vlan": null,

&#x20;   "trunk\_allowed\_vlans": \[ 88 ]

&#x20; } ],

&#x20; "parse\_warnings": \[]

}

