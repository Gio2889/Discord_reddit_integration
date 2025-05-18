# Reddit Discord Bot

A Discord bot that monitors Reddit posts and shares them in a designated Discord channel.

## Introduction

This project is a Reddit Bot that interacts with a Discord server. It monitors specified Reddit posts and communicates them within a designated Discord channel. Features include scheduled checks, manual triggers, and Supabase integration for data persistence.

## Installation

Follow these steps to install and set up the bot:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/reddit-discord-bot.git
   cd reddit-discord-bot
   ```

2. **Install the required packages using pip or uv**.
    ``` pip install -r requirements.txt ```
    or
    ``` uv add -r requirements.txt ```

3. **Run the bot**
    ``` python main.py ```
    or 
    ``` uv run main.py ```


## Configuration
###Environment Variables

Create a `.env` file with the following variables:
``` ini
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=
REDDIT_USERNAME=
REDDIT_PASSWORD=
SUBREDDIT_NAME='Comma Separated string of reddits to search'
TARGET_FLAIRS="Comma separated string of flairs" 
DISCORD_TOKEN = your_discord_token
DISCORD_POST_CHANNEL = channel_id
SUPABASE_URL=supabase_url
SUPABASE_KEY=supabase_api_key
CHECK_INTERVAL=300  # Check interval in seconds (e.g., 300 = 5 minutes)
```

## Project Structure
### Classes and Methods
#### RedditBotManager
Manages the bot's connection to Discord and scheduled tasks.
    
    __init__(Supabase: bool = False)
    Initializes the bot with Discord intents. Set Supabase=True to enable database integration.

    async on_ready()
    Called when the bot connects. Sets up commands and starts scheduled tasks.

    async on_message(message)
    Handles incoming Discord messages.

    @tasks.loop(seconds=20)
    Scheduled task that runs checks every 20 seconds.

    async close()
    Gracefully shuts down the bot.

#### CommandGroup

Handles Reddit monitoring commands via Discord.

    @commands.command(name="hello")
    Responds to !hello with a greeting.

    @commands.command()
    Trigger manual Reddit checks with !checknow.

    async publish_content(post_content: dict, ctx)
    Publishes parsed Reddit posts to the Discord channel.

#### Utility Methods

    async embed_post(parsed_content)
    Creates a Discord embed for a Reddit post.

    async parse_reddit_post(content)
    Parses raw Reddit data into a structured dictionary.

    async get_emoji_by_name(ctx, emoji_name)
    Fetches a custom emoji from the guild by name.

    async add_reactions_to_message(message, emoji_list)
    Adds reactions to a message (e.g., upvote/downvote buttons).

### Usage

    Invite the bot to your Discord server.

    In your authorized channel:

        Use !hello to test the bot.

        Use !checknow to manually trigger a Reddit check.

    New posts matching your criteria will auto-post to the channel.

## License
This project is licensed under the MIT License. See LICENSE for details.
