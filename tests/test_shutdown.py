"""Exercise shutdown on a real event loop without Discord credentials/network."""
import ast
import asyncio
import contextlib
import io
import os
from pathlib import Path
import signal
import unittest
from unittest.mock import AsyncMock


def load_shutdown(bot, cleanup_processes):
    # Import only these functions: importing app.py logs in/configures Discord.
    path = Path(__file__).resolve().parents[1] / 'app' / 'app.py'
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name in {'main', 'cleanup_voice_clients'}]
    scope = dict(asyncio=asyncio, signal=signal, bot=bot,
                 cleanup_processes=cleanup_processes,
                 client_id='test', application_id='test', dictID=0)
    exec(compile(tree, str(path), 'exec'), scope)
    return scope['main']


class FakeBot:
    def __init__(self, start):
        self.start = start
        self.voice_clients = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True


class ShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_signals_disconnect_and_exit_without_blocking(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=sig):
                async def start(_):
                    asyncio.get_running_loop().call_soon(os.kill, os.getpid(), sig)
                    await asyncio.Future()

                bot = FakeBot(start)

                class VoiceClient:
                    channel = None
                    disconnected = False

                    def is_connected(self):
                        return True

                    async def disconnect(self, force):
                        # A second signal during cleanup must not cancel it.
                        os.kill(os.getpid(), sig)
                        await asyncio.sleep(0.02)
                        self.disconnected = True

                voice = VoiceClient()
                bot.voice_clients = [voice]
                cleaned = []
                main = load_shutdown(bot, lambda: cleaned.append(True))
                with contextlib.redirect_stdout(io.StringIO()):
                    await asyncio.wait_for(main(), timeout=1)
                self.assertTrue(voice.disconnected)
                self.assertTrue(bot.closed)
                self.assertEqual(cleaned, [True])

    async def test_startup_failure_still_cleans_up(self):
        bot = FakeBot(AsyncMock(side_effect=RuntimeError('startup failed')))
        cleaned = []
        main = load_shutdown(bot, lambda: cleaned.append(True))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'startup failed'):
                await main()
        self.assertTrue(bot.closed)
        self.assertEqual(cleaned, [True])

    async def test_external_cancellation_is_not_swallowed(self):
        bot = FakeBot(AsyncMock(side_effect=asyncio.CancelledError))
        cleaned = []
        main = load_shutdown(bot, lambda: cleaned.append(True))
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(asyncio.CancelledError):
                await main()
        self.assertTrue(bot.closed)
        self.assertEqual(cleaned, [True])


if __name__ == '__main__':
    unittest.main()
