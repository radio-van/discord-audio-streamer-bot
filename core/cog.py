import math
from copy import copy

import discord
from discord.ext import commands

from audio_sources.youtube import YTDLError, YTDLSource
from .song import Song
from .voice import Voice, VoiceError


class AudioStreamerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state:
            state = Voice(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.suspend())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command can\'t be used in DM channels.')

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    async def cog_command_error(self, ctx: commands.Context,
                                error: commands.CommandError):
        await ctx.send(f'An error occurred: {str(error)}')

    @commands.command(name='join', invoke_without_subcommand=True)
    @commands.has_permissions(manage_guild=True)
    async def _join(self, ctx: commands.Context,
                    *, channel: discord.VoiceChannel = None):
        """
        Joins a voice channel.
        If no channel was specified, it joins your channel.
        """

        if not channel and not ctx.author.voice:
            raise VoiceError('You are neither connected to a voice channel nor specified a channel to join.')

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='leave', aliases=['disconnect'])
    @commands.has_permissions(manage_guild=True)
    async def _leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""

        if not ctx.voice_state.voice:
            return await ctx.send('Not connected to any voice channel.')

        await ctx.voice_state.suspend()
        del self.voice_states[ctx.guild.id]

    @commands.command(name='now', aliases=['current', 'playing'])
    @commands.has_permissions(manage_guild=True)
    async def _now(self, ctx: commands.Context):
        """Displays the currently playing song."""

        if ctx.voice_state.current:
            await ctx.send(
                embed=ctx.voice_state.current.create_embed()
                .add_field(name='Loop', value=ctx.voice_state.loop)
                .add_field(name='Volume', value=int(ctx.voice_state.volume * 100))
            )
        else:
            await ctx.send('Nothing is queued')

    @commands.command(name='pause')
    @commands.has_permissions(manage_guild=True)
    async def _pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='resume')
    @commands.has_permissions(manage_guild=True)
    async def _resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='stop')
    @commands.has_permissions(manage_guild=True)
    async def _stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""

        ctx.voice_state.songs.clear()

        ctx.voice_state.loop = False

        if ctx.voice_client.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name='skip')
    @commands.has_permissions(manage_guild=True)
    async def _skip(self, ctx: commands.Context):
        """Skip a song."""

        if not ctx.voice_state.is_playing:
            return await ctx.send('Not playing any music right now...')

        await ctx.message.add_reaction('⏭')
        ctx.voice_state.skip()

    @commands.command(name='queue')
    @commands.has_permissions(manage_guild=True)
    async def _queue(self, ctx: commands.Context, *, page: int = 1):
        """
        Shows the player's queue.
        You can optionally specify the page to show.
        Each page contains 10 elements.
        """

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += f'`{i}.` [**{song.source.title}**]({song.source.url})\n'

        embed = (
            discord.Embed(
                description=f'**{len(ctx.voice_state.songs)} tracks:**\n\n{queue}',
                color=discord.Color.from_rgb(69, 38, 53))
            .set_footer(text=f'Viewing page {page}/{pages}')
        )
        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    @commands.has_permissions(manage_guild=True)
    async def _shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name='remove')
    @commands.has_permissions(manage_guild=True)
    async def _remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='loop')
    @commands.has_permissions(manage_guild=True)
    async def _loop(self, ctx: commands.Context):
        """Loops/unloops the currently playing song."""

        if not ctx.voice_state.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.send(f'`DEBUG: LOOP is {ctx.voice_state.loop}`')
#       await ctx.send(
#           embed=ctx.voice_state.current.create_embed()
#           .add_field(name='Loop', value=ctx.voice_state.loop)
#           .add_field(name='Volume', value=int(ctx.voice_state.volume * 100))
#       )

        if ctx.voice_state.loop and ctx.voice_state.current.state == 'stream':
            url = ctx.voice_state.current.source.stream_url

            await ctx.send(f'`DEBUG: started downloading {ctx.voice_state.current.source}`')
            await ctx.message.add_reaction('📥')

            ctx.voice_state.current.state = 'downloading'

            await YTDLSource.download(
                loop=self.bot.loop,
                url=url,
            )
            await ctx.send(f'`DEBUG: downloaded {ctx.voice_state.current.source}`')
            ctx.voice_state.current.state = 'downloaded'

        await ctx.message.add_reaction('✅')

    @commands.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def _add(self, ctx: commands.Context, *, search: str = ''):
        """
        Adds a song to playlist.
        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        """
        async with ctx.typing():
            if not ctx.voice_state.voice:
                await ctx.send('`DEBUG: joining voice channel...`')
                await ctx.invoke(self._join)

            song = await self.song_from_yotube(ctx, search)

            await ctx.voice_state.songs.put(song)
            await ctx.send(f'Enqueued {str(song.source)}')

    @commands.command(name='play')
    @commands.has_permissions(manage_guild=True)
    async def _play(self, ctx: commands.Context, *, search: str = ''):
        """
        Streams a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        """

        async with ctx.typing():
            if not ctx.voice_state.voice:
                await ctx.send('`DEBUG: joining voice channel...`')
                await ctx.invoke(self._join)

            song = await self.song_from_yotube(ctx, search)

            if ctx.voice_state.is_playing:
                await ctx.send('`DEBUG: alredy playing smth, replacing song...`')

                previously_added_songs = [
                    copy(song_in_queue) for song_in_queue in ctx.voice_state.songs
                ]
                ctx.voice_state.songs.clear()
                ctx.voice_state.songs.put_nowait(song)
                for previously_added_song in previously_added_songs:
                    ctx.voice_state.songs.put_nowait(previously_added_song)
                del previously_added_songs

                await ctx.invoke(self._skip)
            else:
                await ctx.send('`DEBUG: nothing is playing, async put to SongQueue...`')
                await ctx.voice_state.songs.put(song)

            # if bot was disconnected after timeout, Voice (aka voice_state)
            # object exists, but `audio_player` task is already done and
            # needs to be recreated
            if ctx.voice_state.audio_player.done():
                await ctx.send('`DEBUG: audio player task was done, recreating...`')
                ctx.voice_state.start_player()

    @commands.command(name='volume')
    @commands.has_permissions(manage_guild=True)
    async def _volume(self, ctx: commands.Context, *, volume: int = -1):
        """Sets the volume of the player."""

        if not ctx.voice_state.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        if volume == -1:
            return await ctx.send(f'Current Volume: {ctx.voice_state.volume * 100}% ({ctx.voice_state.volume})')

        if volume > 100 or volume < 0:
            return await ctx.send('Volume must be between 0 and 100')

        ctx.voice_state.volume = volume / 100
        await ctx.send(f'Volume of the player set to {volume}%')

    @commands.command(name='help')
    @commands.has_permissions(manage_guild=True)
    async def _help(self, ctx: commands.Context):
        """Display custom help."""
        help_page = (
            discord.Embed(title='Usage',
                          description=f'**All commands must be used with bot prefix `{ctx.prefix}`!**',
                          color=discord.Color.from_rgb(142, 192, 124))
            .add_field(name='add `URL/search`', value='add `URL` or first suitable `search` to *queue*')
            .add_field(name='play `URL/search`', value='play `URL` or first suitable `search`')
            .add_field(name='pause/resume/stop', value='control playback')
            .add_field(name='skip', value='go to next song in *queue*')
            .add_field(name='loop', value='repeat current song')
            .add_field(name='now', value='show current song')
            .add_field(name='queue', value='show current song *queue*')
            .add_field(name='shuffle', value='shuffle *queue*')
            .add_field(name='remove `NUM`', value='remove `NUM`th song from queue')
            .add_field(name='join `NAME`', value='add bot to your **current** voice channel or to channel `NAME` if provided')
            .add_field(name='leave', value='remove bot from current voice channel')
            .add_field(name='volume `1-100`', value='show current volume or change volume to `1-100`'))

        await ctx.send(embed=help_page)

    @_join.before_invoke
    @_play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

    async def song_from_yotube(self, ctx: commands.Context, search: str):
        if not search:
            raise VoiceError('**Please provide URL or search keywords**')

        try:
            source = await YTDLSource.create_source(
                ctx, search,
                loop=self.bot.loop,
            )
        except YTDLError as e:
            await ctx.send(f'An error occurred while processing this request: {str(e)}')
        else:
            return Song(source=source)
