from __future__ import annotations

from aiohttp import web
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest

from app_v4.net.websmart_client import AsyncWebSmartClient


VALID_CONFIG = "\n".join(["hostname sw01", *["interface ethernet 1"] * 6])
V2_CONFIG = "\n".join(["hostname v2", *["interface ethernet 2"] * 6])


async def _start_server(app: web.Application) -> tuple[web.AppRunner, int]:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    sockets = site._server.sockets
    assert sockets is not None
    return runner, sockets[0].getsockname()[1]


@pytest.mark.asyncio
async def test_traditional_websmart_login_downloads_direct_config():
    seen_login = []

    async def login(request: web.Request) -> web.Response:
        data = await request.post()
        seen_login.append((data["Login"], data["Password"]))
        return web.Response(
            text='<html><input name="Gambit" value="abc123"></html>',
            content_type="text/html",
        )

    async def config(request: web.Request) -> web.Response:
        assert request.query["Gambit"] == "abc123"
        return web.Response(text=VALID_CONFIG, content_type="text/plain")

    app = web.Application()
    app.router.add_post("/iss/redirect.html", login)
    app.router.add_get("/iss.conf", config)
    runner, port = await _start_server(app)

    client = AsyncWebSmartClient("127.0.0.1", port, "admin", "secret", timeout=5)
    try:
        assert await client.connect() is True
        text = await client.get_running_config([])
    finally:
        await client.disconnect()
        await runner.cleanup()

    assert seen_login == [("admin", "secret")]
    assert text == VALID_CONFIG


@pytest.mark.asyncio
async def test_traditional_websmart_submits_backup_form():
    submitted = []

    async def login(request: web.Request) -> web.Response:
        await request.post()
        return web.Response(text="<html>logged in</html>", content_type="text/html")

    async def backup_page(request: web.Request) -> web.Response:
        return web.Response(
            text="""
            <html>
              <form action="/download" method="post">
                <input type="hidden" name="session" value="s1">
                <input type="submit" name="b_save" value="Backup">
              </form>
            </html>
            """,
            content_type="text/html",
        )

    async def download(request: web.Request) -> web.Response:
        data = await request.post()
        submitted.append(dict(data))
        return web.Response(text=VALID_CONFIG, content_type="text/plain")

    app = web.Application()
    app.router.add_post("/iss/redirect.html", login)
    app.router.add_get("/iss/config_file_http.html", backup_page)
    app.router.add_post("/download", download)
    runner, port = await _start_server(app)

    client = AsyncWebSmartClient("127.0.0.1", port, "admin", "secret", timeout=5)
    try:
        assert await client.connect() is True
        text = await client.get_running_config([])
    finally:
        await client.disconnect()
        await runner.cleanup()

    assert submitted == [{"b_save": "Backup", "session": "s1"}]
    assert text == VALID_CONFIG


@pytest.mark.asyncio
async def test_traditional_websmart_login_does_not_follow_redirect_before_gambit():
    seen_config = []

    async def login(request: web.Request) -> web.Response:
        raise web.HTTPFound(location="/iss/main.html")

    async def redirected(request: web.Request) -> web.Response:
        return web.Response(text="login page without token", content_type="text/html")

    async def fallback_login(request: web.Request) -> web.Response:
        return web.Response(text='<html><input name="Gambit" value="legacy-token"></html>', content_type="text/html")

    async def config(request: web.Request) -> web.Response:
        seen_config.append(request.query.get("Gambit"))
        return web.Response(text=VALID_CONFIG, content_type="text/plain")

    app = web.Application()
    app.router.add_post("/iss/redirect.html", login)
    app.router.add_get("/iss/main.html", redirected)
    app.router.add_post("/iss/login.cgi", fallback_login)
    app.router.add_get("/iss.conf", config)
    runner, port = await _start_server(app)

    client = AsyncWebSmartClient("127.0.0.1", port, "admin", "secret", timeout=5)
    try:
        assert await client.connect() is True
        text = await client.get_running_config([])
    finally:
        await client.disconnect()
        await runner.cleanup()

    assert seen_config == ["legacy-token"]
    assert text == VALID_CONFIG


@pytest.mark.asyncio
async def test_traditional_websmart_rejects_short_direct_download_and_falls_back():
    requested = []

    async def login(request: web.Request) -> web.Response:
        return web.Response(text='<html><input name="Gambit" value="abc123"></html>', content_type="text/html")

    async def short_config(request: web.Request) -> web.Response:
        requested.append("iss.conf")
        return web.Response(text="too short", content_type="text/plain")

    async def backup_page(request: web.Request) -> web.Response:
        requested.append("backup-page")
        return web.Response(
            text='<html><form action="/download"><input type="submit" name="b_save" value="Backup"></form></html>',
            content_type="text/html",
        )

    async def download(request: web.Request) -> web.Response:
        requested.append("download")
        return web.Response(text=VALID_CONFIG, content_type="text/plain")

    app = web.Application()
    app.router.add_post("/iss/redirect.html", login)
    app.router.add_get("/iss.conf", short_config)
    app.router.add_get("/iss/config_file_http.html", backup_page)
    app.router.add_post("/download", download)
    runner, port = await _start_server(app)

    client = AsyncWebSmartClient("127.0.0.1", port, "admin", "secret", timeout=5)
    try:
        await client.connect()
        text = await client.get_running_config([])
    finally:
        await client.disconnect()
        await runner.cleanup()

    assert requested == ["iss.conf", "backup-page", "download"]
    assert text == VALID_CONFIG


@pytest.mark.asyncio
async def test_websmart_v2_login_uses_rsa_token_flow():
    seen_params = []
    seen_headers = []
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    escaped_public_pem = public_pem.replace("\n", "\\n")

    async def public_key(request: web.Request) -> web.Response:
        return web.Response(
            text=f'window.web_pub_key = "{escaped_public_pem}";',
            content_type="application/javascript",
        )

    async def login(request: web.Request) -> web.Response:
        seen_params.append(dict(request.query))
        seen_headers.append((request.headers.get("Accept"), request.headers.get("Referer")))
        return web.json_response({"gambit": "v2token"})

    async def config(request: web.Request) -> web.Response:
        assert request.query["Gambit"] == "v2token"
        return web.Response(text=V2_CONFIG, content_type="text/plain")

    app = web.Application()
    app.router.add_get("/iss/specific/web_pub_key_data.js", public_key)
    app.router.add_get("/iss/specific/web_login_data.js", login)
    app.router.add_get("/iss1.conf", config)
    runner, port = await _start_server(app)

    client = AsyncWebSmartClient(
        "127.0.0.1",
        port,
        "manager",
        "friend",
        timeout=5,
        force_v2_only=True,
    )
    try:
        assert await client.connect() is True
        text = await client.get_running_config([])
    finally:
        await client.disconnect()
        await runner.cleanup()

    assert seen_params
    assert seen_params[0]["pelican"]
    assert seen_params[0]["pinkpanther"]
    assert seen_headers == [("application/json, text/plain, */*", f"http://127.0.0.1:{port}/main.html")]
    assert text == V2_CONFIG


@pytest.mark.asyncio
async def test_websmart_v2_rejects_short_iss1_and_falls_back_to_iss_conf():
    requested = []
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    escaped_public_pem = public_pem.replace("\n", "\\n")

    async def public_key(request: web.Request) -> web.Response:
        return web.Response(text=f'window.web_pub_key = "{escaped_public_pem}";', content_type="application/javascript")

    async def login(request: web.Request) -> web.Response:
        return web.json_response({"gambit": "v2token"})

    async def iss1(request: web.Request) -> web.Response:
        requested.append("iss1")
        return web.Response(text="short", content_type="text/plain")

    async def iss(request: web.Request) -> web.Response:
        requested.append("iss")
        return web.Response(text=V2_CONFIG, content_type="text/plain")

    app = web.Application()
    app.router.add_get("/iss/specific/web_pub_key_data.js", public_key)
    app.router.add_get("/iss/specific/web_login_data.js", login)
    app.router.add_get("/iss1.conf", iss1)
    app.router.add_get("/iss.conf", iss)
    runner, port = await _start_server(app)

    client = AsyncWebSmartClient("127.0.0.1", port, "manager", "friend", timeout=5, force_v2_only=True)
    try:
        await client.connect()
        text = await client.get_running_config([])
    finally:
        await client.disconnect()
        await runner.cleanup()

    assert requested == ["iss1", "iss"]
    assert text == V2_CONFIG
