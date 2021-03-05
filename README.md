# Discord AudioStreamer Bot

Mostly based on examples from [discord.py](https://github.com/Rapptz/discord.py) and [this](https://gist.github.com/guac420/bc612fd3a35cd00ddc1c221c560daa01) and [this](https://gist.github.com/vbe0201/ade9b80f2d3b64643d854938d40a0a2d) gists.

Streams audio from YouTube (or any other [source supported by youtube-dl](https://rg3.github.io/youtube-dl/supportedsites.html)) url to given Discord voice channel.

# Dependencies
- python >3.8
- ffmpeg

python packages:  
`pip install -r requirements.txt`
- discord
- pynacl
- youtube-dl

# Usage
- Create Application and Bot at [discord dev portal](https://discord.com/developers/applications)
- obtain bot token
- authorize bot using `https://discordapp.com/oauth2/authorize?client_id=BOT_ID&scope=bot&permissions=36700928`  

  `BOT_ID` is printed after connection (see below)  
  `permissions` are for voice communication only  

## as stand-alone
```shell
python3 bot.py BOT_NAME BOT_TOKEN
```

## as python module
see `bot.py`

# Bot controls
`BOT_NAME` becomes bot **prefix**, i.e. if you named bot `music_bot`, then all commands should be typed as `music_bot.COMMAND`.  
All bot commands are available via `PREFIX.help`
