import asyncio
import os
from async_timeout import timeout

from discord import FFmpegPCMAudio
from discord.ext import commands

from audio_sources.youtube import YTDLSource
from .song import SongQueue


SONG_QUEUE_TIMEOUT = 600  # 5 min
# SONG_QUEUE_TIMEOUT = 30  # 30 sec


class Voice:
    """
    Represents Discord VoiceState object and allows
    to control playback: queue, volume, looping, etc.
    """
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.next = asyncio.Event()
        self.songs = SongQueue()
        self.voice = None

        self._loop = False
        self._volume = 0.5

        # create EventLoop with player task
        self.start_player()

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

        if not self.loop:
            # throw away downloaded file when loop is off
            # or song was skipped
            if os.path.isfile(f'{self.bot.command_prefix}.mp3'.replace('..', '.')):
                os.remove(f'{self.bot.command_prefix}.mp3'.replace('..', '.'))

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = self.current.source.volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()

            if self.loop:
                # YTDLSource(PCMVolumeTransformer(AudioSource)) can't be
                # rewinded, the only way is to recreate it with the same
                # source
                if self.current.state == 'downloaded':
                    await self.current.source.channel.send(
                        f'`DEBUG: recreating source from local file for {self.current.source}`'
                    )
                    recreated_source = FFmpegPCMAudio(f'{self.bot.command_prefix}.mp3'.replace('..', '.'))
                else:
                    await self.current.source.channel.send(
                        f'`DEBUG: recreating source from streaming url for {self.current.source}`'
                    )
                    recreated_source = FFmpegPCMAudio(
                        self.current.source.stream_url,
                        **YTDLSource.FFMPEG_OPTIONS,
                    )
                # if FFmpegPCMAudio fails to read source (e.g. file is missing or
                # failed to connect to server), .read() returns b''
                if not recreated_source.read():
                    if self.current.state == 'downloaded':
                        await self.current.source.channel.send(
                            f'`DEBUG: Failed to read local file for {self.current.source}`'
                        )
                    else:
                        await self.current.source.channel.send(
                            f'`DEBUG: Failed to recreate stream for {self.current.source}`'
                        )
                    self.loop = False
                    self.voice.stop()
                    self.next.set()
                else:
                    self.current.source = YTDLSource(
                        self._ctx,
                        recreated_source,
                        data=self.current.source.data,
                        volume=self.volume,
                    )
                    self.voice.play(self.current.source, after=self.play_next_song)
            else:
                # Try to get the next song from SongQueue within
                # given timeout. If no song will be added to the
                # queue in time, the player will disconnect due
                # to performance reasons.
                try:
                    async with timeout(SONG_QUEUE_TIMEOUT):
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    await self.current.source.channel.send(
                        f'No new songs in queue for {SONG_QUEUE_TIMEOUT} seconds. Bot now disconnects.'
                    )
                    self.bot.loop.create_task(self.suspend())
                    self.exists = False
                    return

                # feedback to Discord (feedback on loop can produce spam)
                await self.current.source.channel.send(
                    embed=self.current.create_embed()
                    .add_field(name='Loop', value=self.loop)
                    .add_field(name='Volume', value=int(self.volume * 100))
                )

                self.voice.play(self.current.source, after=self.play_next_song)

            await self.next.wait()

    def start_player(self):
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        if self.is_playing:
            self.loop = False
            self.voice.stop()

    async def suspend(self):
        self.current = None
        self.loop = False
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None


class VoiceError(Exception):
    pass
