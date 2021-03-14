import asyncio
import itertools
import random

import discord

from audio_sources.youtube import YTDLSource


class Song:
    """
    Represents Song object, created from various
    (in this case YouTube) audio sources.
    """
    # reduce memory usage
    __slots__ = ('source', 'state')

    def __init__(self, source: YTDLSource):
        self.source = source
        self.state = 'stream'

    def create_embed(self):
        """
        Formats Discord Embed message form prettier output
        """
        embed = (discord
                 .Embed(title='Now playing',
                        description=f'```css\n{self.source.title}\n```',
                        color=discord.Color.from_rgb(27, 52, 53))
                 .add_field(name='Duration', value=self.source.duration)
                 .add_field(name='Source', value=f'[Click]({self.source.url})' if self.state == 'stream' else self.state)
                 .set_thumbnail(url=self.source.thumbnail))

        return embed


class SongQueue(asyncio.Queue):
    """
    Represents queue of songs aka playlist
    """
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(
                itertools.islice(self._queue, item.start, item.stop, item.step)
            )
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]
