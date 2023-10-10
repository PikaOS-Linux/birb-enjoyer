import asyncio
import io
import os
import subprocess
import aiofiles
import aiohttp

import nextcord
import qbittorrentapi
from nextcord.ext import commands
import requests

from internal_tools.configuration import CONFIG
from internal_tools.discord import *


class TorrentCreator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.qbt_api = qbittorrentapi.Client(
            **CONFIG["TORRENT_CREATOR"]["QBT_API_CONN_INFO"]
        )

    async def cog_application_command_check(self, interaction: nextcord.Interaction):
        """
        Everyone can use this.
        """
        return True

    def is_valid_file_url(self, file_url: str):
        try:
            response = requests.head(file_url)
            if response.status_code == 200:
                filename = file_url.rsplit("/", 1)[1]
                if "?" in filename:
                    filename = filename.split("?", 1)[0]

                if "." in filename:
                    return True

        except Exception:
            pass

        return False

    async def create_torrent(self, file_url: str):
        if not os.path.isdir("./temp"):
            os.mkdir("temp")

        if not os.path.isdir("./torrents"):
            os.mkdir("torrents")

        if "Birb Enjoyer" not in self.qbt_api.torrent_tags.tags:
            self.qbt_api.torrents_create_tags("Birb Enjoyer")

        filename = file_url.rsplit("/", 1)[1]
        if "?" in filename:
            filename = filename.split("?", 1)[0]

        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as resp:
                async with aiofiles.open(
                    "./temp/" + filename,
                    mode="wb+",
                ) as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        await f.write(chunk)

        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: subprocess.Popen(
                f'./.venv/bin/py3createtorrent ./temp/{filename} -o torrents/ --quiet --node router.bittorrent.com,8991 -p 512 -c "Created by Birb Enjoyer" -f --md5 --webseed {file_url}',
                shell=True,
            ).communicate(),
        )

        async with aiofiles.open(
            "./temp/" + filename,
            mode="rb",
        ) as src:
            async with aiofiles.open(
                "/mnt/home/Drive/torrents/data/" + filename,
                mode="wb+",
            ) as dst:
                while True:
                    chunk = await src.read(8192)
                    if not chunk:
                        break  # Reached the end of the file

                    await dst.write(chunk)

        os.remove(f"./temp/{filename}")

        async with aiofiles.open(
            f"./torrents/{filename}.torrent",
            mode="rb",
        ) as f:
            torrent_file_data = await f.read()

        os.remove(f"./torrents/{filename}.torrent")

        self.qbt_api.torrents_add(
            torrent_files=torrent_file_data,
            tags="Birb Enjoyer",
            seeding_time_limit=10080,
        )

        return nextcord.File(io.BytesIO(torrent_file_data), f"{filename}.torrent")

    @nextcord.slash_command(
        "create-torrent",
        description="Takes a URL to a file, downloads it, makes a Torrent from it, returns you the .torrent file.",
        dm_permission=False,
        default_member_permissions=nextcord.Permissions(administrator=True),
    )
    async def create_torrent_command(
        self, interaction: nextcord.Interaction, file_url: str
    ):
        if (
            not isinstance(interaction.channel, nextcord.TextChannel)
            or interaction.user is None
        ):
            return

        if not self.is_valid_file_url(file_url):
            await interaction.send("Thats not a valid file URL", ephemeral=True)
            return

        await interaction.send("Ok, working on it. One sec.")

        torrent_file = await self.create_torrent(file_url)
        await interaction.channel.send(interaction.user.mention, file=torrent_file)


async def setup(bot):
    bot.add_cog(TorrentCreator(bot))
