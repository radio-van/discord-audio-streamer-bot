import sys

from discord.ext import commands

from core.cog import AudioStreamerCog


if len(sys.argv) != 3:
    print('Usage: bot.py <bot name> <bot token>')
    sys.exit(2)

bot_name = sys.argv[1]
bot_token = sys.argv[2]

bot = commands.Bot(
    description=f'AudioStreamer Bot {bot_name}',
    command_prefix=f'{bot_name}.',
    help_command=None,
)
bot.add_cog(AudioStreamerCog(bot))


@bot.event
async def on_ready():
    print(f'Bot {bot_name} logged in as:\n{bot.user.name}\n{bot.user.id}')


bot.run(f'{bot_token}')
