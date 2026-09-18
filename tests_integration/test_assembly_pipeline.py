"""Integration tests: the real assembly pipeline driven in fresh subprocesses.

Each test spawns a clean interpreter from a temporary working directory (no
``config.yaml``, so ``AppConfig`` defaults apply) and exercises a real
entrypoint path: a real ``settings.configure()`` + ``django.setup()``,
explicitly-registered plugin hooks (v3: no auto-discovery), and the real
ASGI/CLI surfaces. This complements the in-process unit tests, which stub
``settings``/``django.setup`` to make the pipeline runnable.
"""

import json
import subprocess
import sys
from typing import Any

import pytest

pytestmark = pytest.mark.integration

_TIMEOUT_SECONDS = 180


def _run(code: str, tmp_path: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )


def test_real_assembly_configures_django(tmp_path: Any) -> None:
    """create_application() assembles the real settings manifest end-to-end."""

    code = (
        "from do_as_beginner.asgi import create_application\n"
        "from django.conf import settings\n"
        "app = create_application()\n"
        "print('configured:', settings.configured)\n"
        "print('has-admin:', 'django.contrib.admin' in settings.INSTALLED_APPS)\n"
        "print('has-blobs:', 'do_as_beginner.blobs' in settings.INSTALLED_APPS)\n"
        "print('has-tasks:', 'do_as_beginner.tasks' in settings.INSTALLED_APPS)\n"
        "print('engine:', settings.DATABASES['default']['ENGINE'])\n"
        "print('root-urlconf:', settings.ROOT_URLCONF)\n"
    )
    proc = _run(code, tmp_path)

    assert proc.returncode == 0, proc.stderr
    lines = dict(line.split(": ", 1) for line in proc.stdout.splitlines())
    assert lines["configured"] == "True"
    assert lines["has-admin"] == "True"
    assert lines["has-blobs"] == "True"
    assert lines["has-tasks"] == "True"
    assert lines["engine"] == "django_async_backend.db.backends.postgresql"
    assert lines["root-urlconf"] == "do_as_beginner.server.core.routes"


def test_django_check_passes_through_cli(tmp_path: Any) -> None:
    """``app django check`` runs Django's system checks against the real assembly."""

    code = (
        "import sys\nsys.argv = ['app', 'django', 'check']\nfrom do_as_beginner.asgi import entrypoint\nentrypoint()\n"
    )
    proc = _run(code, tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert "no issues" in proc.stdout


def test_cli_help_lists_builtin_command_groups(tmp_path: Any) -> None:
    """``app --help`` shows the root group with every built-in sub-group."""

    code = "import sys\nsys.argv = ['app', '--help']\nfrom do_as_beginner.asgi import entrypoint\nentrypoint()\n"
    proc = _run(code, tmp_path)

    assert proc.returncode == 0, proc.stderr
    for command in ("run", "auth", "contenttypes", "sessions", "staticfiles", "django"):
        assert command in proc.stdout


def test_http_request_over_asgi_app_returns_json_envelope(tmp_path: Any) -> None:
    """A raw ASGI GET /system/health/ round-trips wrapper proxy -> Django -> controller."""

    code = (
        "import asyncio\n"
        "import json\n"
        "from do_as_beginner.asgi import create_application\n"
        "app = create_application()\n"
        "async def main():\n"
        "    messages = []\n"
        "    state = {'requested': False}\n"
        "    async def receive():\n"
        "        if not state['requested']:\n"
        "            state['requested'] = True\n"
        "            return {'type': 'http.request', 'body': b'', 'more_body': False}\n"
        "        while not any(m['type'] == 'http.response.body' for m in messages):\n"
        "            await asyncio.sleep(0.01)\n"
        "        return {'type': 'http.disconnect'}\n"
        "    async def send(message):\n"
        "        messages.append(message)\n"
        "    scope = {\n"
        "        'type': 'http',\n"
        "        'asgi': {'version': '3.0', 'spec_version': '2.3'},\n"
        "        'http_version': '1.1',\n"
        "        'method': 'GET',\n"
        "        'scheme': 'http',\n"
        "        'path': '/system/health/',\n"
        "        'raw_path': b'/system/health/',\n"
        "        'query_string': b'',\n"
        "        'root_path': '',\n"
        "        'headers': [(b'host', b'testserver'), (b'accept', b'application/json')],\n"
        "        'client': ('127.0.0.1', 51000),\n"
        "        'server': ('testserver', 80),\n"
        "    }\n"
        "    await app(scope, receive, send)\n"
        "    return messages\n"
        "messages = asyncio.run(main())\n"
        "start = next(m for m in messages if m['type'] == 'http.response.start')\n"
        "body = next(m for m in messages if m['type'] == 'http.response.body')\n"
        "print('status:', start['status'])\n"
        "print('body:', body['body'].decode())\n"
    )
    proc = _run(code, tmp_path)

    assert proc.returncode == 0, proc.stderr
    lines = dict(line.split(": ", 1) for line in proc.stdout.splitlines() if line.startswith(("status: ", "body: ")))
    assert lines["status"] == "200"
    envelope = json.loads(lines["body"])
    assert envelope["code"] == 200
    assert envelope["message"] == "ok"


def test_asgi_lifespan_startup_and_shutdown_complete(tmp_path: Any) -> None:
    """The real app completes the lifespan protocol (plugin ``__lifespan__`` hooks attached)."""

    code = (
        "import asyncio\n"
        "from do_as_beginner.asgi import create_application\n"
        "app = create_application()\n"
        "async def main():\n"
        "    sent = []\n"
        "    incoming = iter([{'type': 'lifespan.startup'}, {'type': 'lifespan.shutdown'}])\n"
        "    async def receive():\n"
        "        return next(incoming)\n"
        "    async def send(message):\n"
        "        sent.append(message)\n"
        "    await app({'type': 'lifespan'}, receive, send)\n"
        "    for message in sent:\n"
        "        print('event:', message['type'])\n"
        "asyncio.run(main())\n"
    )
    proc = _run(code, tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == [
        "event: lifespan.startup.complete",
        "event: lifespan.shutdown.complete",
    ]


def test_user_plugin_registration_wires_di_and_cli(tmp_path: Any) -> None:
    """A user-defined plugin registered via the constructor is wired end-to-end.

    v3 registration is explicit: ``AppConfigCore(UserPlugin())``. The subprocess
    drives the real pipeline (settings.configure + django.setup), then executes
    the root group; ``on_app_init`` registers into DI and the ``on_cli_init``
    command runs, resolving the DI registration.
    """

    code = (
        "import sys\n"
        "sys.argv = ['app', 'user-ping']\n"
        "from do_as_beginner.server.core import AppPluginProtocol, CLIPluginProtocol\n"
        "from do_as_beginner.server.depi import Container, DI\n"
        "from do_as_beginner.server.setup import AppConfigCore\n"
        "class UserPlugin(AppPluginProtocol, CLIPluginProtocol):\n"
        "    def on_app_init(self, container: Container) -> None:\n"
        "        container.register('user-plugin-ok', key='user_marker')\n"
        "    def on_cli_init(self, group) -> None:\n"
        "        @group.command(name='user-ping')\n"
        "        def ping() -> None:\n"
        "            print('USER_PING_OK')\n"
        "            print('marker:', DI.get_default_container().get('user_marker'))\n"
        "core = AppConfigCore(UserPlugin())\n"
        "core.setup()\n"
        "from do_as_beginner.server.cli.command import group\n"
        "group()\n"
    )
    proc = _run(code, tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert "USER_PING_OK" in proc.stdout
    assert "marker: user-plugin-ok" in proc.stdout
