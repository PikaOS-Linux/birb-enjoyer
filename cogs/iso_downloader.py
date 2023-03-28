import os
from datetime import datetime
from typing import List

import aiofiles
import aiohttp
import nextcord
from nextcord.ext import commands, tasks

from internal_tools.configuration import CONFIG
from internal_tools.discord import *


class IsoEntry:
    def __init__(
        self,
        name: str,
        size: int,
        url: str,
        mod_time: str,
        mode: int,
        is_dir: bool,
        is_symlink: bool,
    ) -> None:
        self.name: str = name
        self.size: int = size
        self.url: str = url
        self.mod_time: datetime = datetime.fromisoformat(mod_time.rsplit(".", 1)[0])
        self.mode: int = mode
        self.is_dir: bool = is_dir
        self.is_symlink: bool = is_symlink


class IsoDownloader(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.update_isos.start()

    async def cog_application_command_check(self, interaction: nextcord.Interaction):
        """
        Everyone can use this.
        """
        return True

    async def log(self, msg: str):
        async with aiohttp.ClientSession() as session:
            webhook = nextcord.Webhook.from_url(
                CONFIG["ISO_DOWNLOADER"]["LOG_WEBHOOK_URL"], session=session
            )

            await webhook.send(msg)

    async def get_available_isos(self):
        async with aiohttp.ClientSession() as session:
            response = await session.get(
                CONFIG["ISO_DOWNLOADER"]["BASE_URL"],
                headers={
                    "Accept": "application/json",
                },
            )

            data: List[IsoEntry] = []
            for entry in await response.json():
                data.append(IsoEntry(**entry))

            return data

    @tasks.loop(minutes=3)
    async def update_isos(self):
        downloaded = {
            x.name: datetime.fromtimestamp(x.stat().st_mtime)
            for x in os.scandir(CONFIG["ISO_DOWNLOADER"]["ISO_PATH"])
        }

        for entry in await self.get_available_isos():
            if entry.name.endswith(".iso"):
                if (
                    entry.name not in downloaded
                    or entry.mod_time > downloaded[entry.name]
                ):
                    try:
                        os.remove(CONFIG["ISO_DOWNLOADER"]["ISO_PATH"] + entry.name)
                    except:
                        pass

                    async with aiohttp.ClientSession() as session:
                        url = CONFIG["ISO_DOWNLOADER"]["BASE_URL"] + entry.name
                        async with session.get(url) as resp:
                            async with aiofiles.open(
                                CONFIG["ISO_DOWNLOADER"]["ISO_PATH"] + entry.name,
                                mode="wb",
                            ) as f:
                                await f.write(await resp.read())

                                await self.log(
                                    f"Downloaded newest version of `{entry.name}` which was modified last at: <t:{int(entry.mod_time.timestamp())}>"
                                )

    @nextcord.slash_command(
        "iso-downloader",
        dm_permission=False,
        default_member_permissions=nextcord.Permissions(administrator=True),
    )
    async def top_command(self, interaction: nextcord.Interaction):
        ...

    @top_command.subcommand("list-local", description="Shows all downloaded ISOs")
    async def list_local(self, interaction: nextcord.Interaction):
        await interaction.send(
            embed=fancy_embed(
                "Downloaded ISOs",
                description="\n".join(os.listdir(CONFIG["ISO_DOWNLOADER"]["ISO_PATH"])),
            )
        )

    @top_command.subcommand(
        "list-remote", description="Shows all available for download ISOs"
    )
    async def list_remote(self, interaction: nextcord.Interaction):
        await interaction.send(
            embed=fancy_embed(
                "Remote ISOs",
                description="\n".join(
                    [x.name for x in await self.get_available_isos() if x.name.endswith(".iso")]
                ),
            )
        )


async def setup(bot):
    bot.add_cog(IsoDownloader(bot))
