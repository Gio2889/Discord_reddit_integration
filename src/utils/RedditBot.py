import os
import discord
from discord.ext import tasks, commands
from RedditBot import RedditMonitor

class RedditBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix='(.)(.)', intents=intents)
        self.reddit_monitor = RedditMonitor()
        self.post_channel_id = int(os.getenv('DISCORD_POST_CHANNEL'))
        self.check_interval = int(os.getenv('CHECK_INTERVAL'))# 2 hours in seconds

    async def setup_hook(self):
        await self.reddit_monitor.initialize()
        self.post_reddit_updates.start()

    def format_reddit_post(self, content):
        """Convert Reddit content to Discord-friendly format"""
        if "**Link:** http" in content:
            url = content.split("**Link:** ")[1]
            if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                return None, url  # Return separate image URL
        return discord.Embed(description=content), None

    @tasks.loop(seconds=self.check_interval)
    async def post_reddit_updates(self):
        channel = self.get_channel(self.post_channel_id)
        if not channel:
            return

        new_posts = await self.reddit_monitor.get_subred()
        for post_content in new_posts:
            try:
                embed, image_url = self.format_reddit_post(post_content)
                
                if image_url:
                    await channel.send(image_url)
                elif embed:
                    await channel.send(embed=embed)
                
                await asyncio.sleep(5)  # Rate limit protection
            except Exception as e:
                print(f"Failed to post content: {e}")

    @post_reddit_updates.before_loop
    async def before_post_updates(self):
        await self.wait_until_ready()

    @commands.command()
    async def checknow(ctx):
        """Manually trigger Reddit check"""
        await ctx.send("Checking for new posts...")
        await self.post_reddit_updates()

    async def close(self):
        await self.reddit_monitor.close()
        await super().close()

if __name__ == '__main__':
    bot = RedditBot()
    bot.run('')