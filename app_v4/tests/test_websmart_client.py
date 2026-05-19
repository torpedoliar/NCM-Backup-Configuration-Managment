from __future__ import annotations

from aiohttp import web
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest

from app_v4.net.websmart_client import AsyncWebSmartClient


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
        return web.Response(text="hostname sw01\ninterface 1", content_type="text/plain")

    app = web.Application()
    app.router.add_post("/iss/redirect.html", login)
    app.router.add_get("/iss1.conf", config)
    runner, port = await _start_server(app)

    client = AsyncWebSmartClient("127.0.0.1", port, "admin", "secret", timeout=5)
    try:
        assert await client.connect() is True
        text = await client.get_running_config([])
    finally:
        await client.disconnect()
        await runner.cleanup()

    assert seen_login == [("admin", "secret")]
    assert text == "hostname sw01\ninterface 1"


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
        return web.Response(text="sysname sw-form\nconfig line", content_type="text/plain")

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
    assert text == "sysname sw-form\nconfig line"


@pytest.mark.asyncio
async def test_websmart_v2_login_uses_rsa_token_flow():
    seen_params = []
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
        return web.json_response({"gambit": "v2token"})

    async def config(request: web.Request) -> web.Response:
        assert request.query["Gambit"] == "v2token"
        return web.Response(text="hostname v2\ninterface 2", content_type="text/plain")

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
    assert text == "hostname v2\ninterface 2"
