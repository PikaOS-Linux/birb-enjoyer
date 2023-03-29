import os
import datetime
from typing import List

import aiofiles
import aiohttp
import nextcord
from nextcord.ext import commands, tasks

from internal_tools.configuration import CONFIG, JsonDictSaver
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
        self.mod_time: datetime.datetime = datetime.datetime.fromisoformat(
            mod_time.rsplit(".", 1)[0]
        )
        self.mode: int = mode
        self.is_dir: bool = is_dir
        self.is_symlink: bool = is_symlink


class IsoDownloader(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.isos_to_keep = JsonDictSaver("isos_to_keep")

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

    def needs_update_or_download(self, entry: IsoEntry):
        downloaded = {
            x.name: datetime.datetime.fromtimestamp(x.stat().st_mtime)
            for x in os.scandir(CONFIG["ISO_DOWNLOADER"]["ISO_PATH"])
        }

        if entry.name not in downloaded or entry.mod_time > downloaded[entry.name]:
            if (
                entry.mod_time.date()
                > datetime.datetime.utcnow().date() - datetime.timedelta(days=3)
            ):
                return True
            elif entry.name in self.isos_to_keep:
                return True
            else:
                return False
        elif (
            datetime.datetime.utcnow().date() - entry.mod_time.date()
            >= datetime.timedelta(days=3)
        ):
            return False

        return None

    async def download_iso(self, url: str):
        filename = url.rsplit("/", 1)[1]

        try:
            os.remove(CONFIG["ISO_DOWNLOADER"]["ISO_PATH"] + filename)
        except:
            pass

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                async with aiofiles.open(
                    CONFIG["ISO_DOWNLOADER"]["ISO_PATH"] + filename,
                    mode="wb",
                ) as f:
                    await f.write(await resp.read())

    @tasks.loop(minutes=3)
    async def update_isos(self):
        for entry in await self.get_available_isos():
            if entry.name.endswith(".iso"):
                match self.needs_update_or_download(entry):
                    case None:
                        continue

                    case True:
                        await self.download_iso(
                            CONFIG["ISO_DOWNLOADER"]["BASE_URL"] + entry.name
                        )

                        await self.log(
                            f"Downloaded newest version of `{entry.name}` which was modified last at: <t:{int(entry.mod_time.timestamp())}>"
                        )

                    case False:
                        try:
                            os.remove(CONFIG["ISO_DOWNLOADER"]["ISO_PATH"] + entry.name)
                        except:
                            pass

                        await self.log(f"Deleted old ISO `{entry.name}`")

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
                    [
                        x.name
                        for x in await self.get_available_isos()
                        if x.name.endswith(".iso")
                    ]
                ),
            )
        )

    @top_command.subcommand(
        "manually-keep-iso", description="Keep this ISO, even if its older than 3 days."
    )
    async def manually_keep_iso(self, interaction: nextcord.Interaction, filename: str):
        self.isos_to_keep[filename] = True
        self.isos_to_keep.save()

        msg = f"Keeping `{filename}`, even after 3 days. Also downloading it in case it has not been already."
        await interaction.send(msg)
        await self.log(msg)

    @top_command.subcommand(
        "stop-keeping-iso", description="Stop keeping this ISO for longer than 3 days."
    )
    async def stop_keeping_iso(self, interaction: nextcord.Interaction, filename: str):
        del self.isos_to_keep[filename]
        self.isos_to_keep.save()

        msg = f"Stopped keeping `{filename}` for longer than 3 days."
        await interaction.send(msg)
        await self.log(msg)


async def setup(bot):
    bot.add_cog(IsoDownloader(bot))
