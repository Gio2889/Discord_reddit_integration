"""
Main entry point for running the Reddit Bot.

This script initializes and runs the RedditBotManager.

Returns:
    None

Raises:
    Exception: If there is an error in running the bot.
"""

import os
from utils.RedditBot import RedditBotManager

os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Create an instance of RedditBotManager
    bot = RedditBotManager()
    # Run the bot using the provided Discord token from the environment variables
    bot.run(os.getenv("DISCORD_TOKEN"))
