import asyncio
from async_timeout import timeout

from discord import FFmpegPCMAudio
from discord.ext import commands

from audio_sources.youtube import YTDLSource
from .song import SongQueue


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
        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

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
            self.now = None

            if self.loop:
                self.now = FFmpegPCMAudio(
                    self.current.source.stream_url,
                    **YTDLSource.FFMPEG_OPTIONS,
                )
                self.voice.play(self.now, after=self.play_next_song)
            else:
                # Try to get the next song from SongQueue within
                # given timeout. If no song will be added to the
                # queue in time, the player will disconnect due
                # to performance reasons.
                try:
                    async with timeout(180):  # 3 minutes
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    self.exists = False
                    return

                self.current.source.volume = self._volume
                self.voice.play(self.current.source, after=self.play_next_song)

                # feedback to Discord
                await self.current.source.channel.send(
                    embed=self.current.create_embed()
                    .add_field(name='Loop', value=self.loop)
                    .add_field(name='Volume', value=int(self.volume * 100))
                )

            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None


class VoiceError(Exception):
    pass
