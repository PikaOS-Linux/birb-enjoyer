import nextcord
from nextcord.ext import commands

from internal_tools.discord import *


class TorrentCreator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_application_command_check(self, interaction: nextcord.Interaction):
        """
        Everyone can use this.
        """
        return True


async def setup(bot):
    bot.add_cog(TorrentCreator(bot))
