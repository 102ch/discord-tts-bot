"""Voice lifecycle regressions, without Discord credentials or a live connection."""
import ast
import asyncio
from collections import defaultdict, deque
import logging
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock


def load_functions(names, **scope):
    path = Path(__file__).resolve().parents[1] / 'app' / 'app.py'
    tree = ast.parse(path.read_text())
    tree.body = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    for node in tree.body:
        node.decorator_list = []
    scope.update(asyncio=asyncio, os=os, logger=logging.getLogger('test'),
                 discord=NS(Interaction=object, Member=object, VoiceState=object,
                            opus=NS(is_loaded=lambda: True)))
    exec(compile(tree, str(path), 'exec'), scope)
    return scope


class VoiceTests(unittest.IsolatedAsyncioTestCase):
    def setup_scope(self, connected=False):
        channel = NS(id=20, name='test')
        voice = NS(channel=channel, is_connected=lambda: connected, disconnect=AsyncMock(), latency=0)
        guild = NS(id=1, voice_client=voice)
        interaction = NS(guild=guild, channel_id=30, user=NS(voice=NS(channel=channel)),
                         response=NS(defer=AsyncMock()), followup=NS(send=AsyncMock()))
        result = NS(is_connected=lambda: True, latency=0)
        scope = load_functions({'join', 'dc', 'on_voice_state_update'},
            voice_operations=set(), connecting_channels=set(), currentChannel={},
            queue_dict=defaultdict(deque), connect_with_retry=AsyncMock(return_value=result),
            cleanup_stale_voice_client=AsyncMock(), bot=NS(user=NS(id=99)), jtalk=AsyncMock())
        return scope, interaction, voice

    async def test_stale_same_channel_can_rejoin(self):
        scope, interaction, voice = self.setup_scope()
        await scope['join'](interaction)
        voice.disconnect.assert_awaited_once_with(force=True)
        scope['connect_with_retry'].assert_awaited_once()
        self.assertEqual(scope['currentChannel'], {1: 30})
        self.assertFalse(scope['voice_operations'])

    async def test_connected_same_channel_is_untouched(self):
        scope, interaction, voice = self.setup_scope(connected=True)
        await scope['join'](interaction)
        voice.disconnect.assert_not_awaited()
        scope['connect_with_retry'].assert_not_awaited()
        self.assertFalse(scope['voice_operations'])

    async def test_concurrent_join_and_dc_cannot_interrupt_connect(self):
        scope, interaction, voice = self.setup_scope()
        interaction.guild.voice_client = None
        started, finish = asyncio.Event(), asyncio.Event()
        async def connect(*args, **kwargs):
            started.set()
            await finish.wait()
            return NS(is_connected=lambda: True, latency=0)
        scope['connect_with_retry'].side_effect = connect
        first = asyncio.create_task(scope['join'](interaction))
        await started.wait()
        try:
            await scope['join'](interaction)
            await scope['dc'](interaction)
            self.assertEqual(scope['connect_with_retry'].await_count, 1)
            self.assertEqual(scope['voice_operations'], {1})
        finally:
            finish.set()
            await first
        self.assertFalse(scope['voice_operations'])

    async def test_failed_connection_releases_guard_and_channel(self):
        scope, interaction, _ = self.setup_scope()
        interaction.guild.voice_client = None
        scope['connect_with_retry'].side_effect = RuntimeError('test failure')
        await scope['join'](interaction)
        self.assertFalse(scope['voice_operations'])
        self.assertFalse(scope['connecting_channels'])
        self.assertFalse(scope['currentChannel'])
        scope['cleanup_stale_voice_client'].assert_awaited_once()

    async def test_bot_voice_events_do_not_trigger_synthesis(self):
        scope, interaction, _ = self.setup_scope()
        scope['currentChannel'][1] = 30
        await scope['on_voice_state_update'](NS(id=99, guild=interaction.guild),
                                            NS(channel=None), NS(channel=NS(id=20)))
        scope['jtalk'].assert_not_awaited()

    async def test_synthesis_does_not_block_event_loop_and_serializes(self):
        started, release = threading.Event(), threading.Event()
        calls = []
        def synthesize(text):
            calls.append(text)
            started.set()
            if not release.wait(2):
                raise RuntimeError('Event loop could not release worker')
            return text
        scope = load_functions({'jtalk'}, synthesis_lock=asyncio.Lock(), synthesize=synthesize)
        first = asyncio.create_task(scope['jtalk']('first'))
        second = None
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(.005)
            self.assertTrue(started.is_set())
            second = asyncio.create_task(scope['jtalk']('second'))
            await asyncio.sleep(.02)
            self.assertFalse(first.done())
            self.assertEqual(calls, ['first'])
        finally:
            release.set()
            await first
            if second:
                await second
        self.assertEqual(calls, ['first', 'second'])

    async def test_cancelled_synthesis_removes_unused_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'out.wav'
            started, release = threading.Event(), threading.Event()
            def synthesize(text):
                started.set()
                release.wait(2)
                output.write_bytes(b'audio')
                return str(output)
            scope = load_functions({'jtalk'}, synthesis_lock=asyncio.Lock(), synthesize=synthesize)
            task = asyncio.create_task(scope['jtalk']('test'))
            try:
                for _ in range(100):
                    if started.is_set():
                        break
                    await asyncio.sleep(.005)
                self.assertTrue(started.is_set())
                task.cancel()
                await asyncio.sleep(.01)
            finally:
                release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertFalse(output.exists())
