import pytest
import asyncio
import sys 
import os
from unittest.mock import AsyncMock, MagicMock, patch, mock_open, ANY
from io import BytesIO 

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import discord
    from discord.ext import commands
except ImportError:
    class DiscordObject:
        def __init__(self, id=None, name=None):
            self.id = id or MagicMock()
            self.name = name or MagicMock()

    class Guild(DiscordObject):
        def __init__(self, id=None, name=None, emojis=None):
            super().__init__(id, name)
            self.emojis = emojis or []

    class TextChannel(DiscordObject):
         def __init__(self, id=None, name=None, guild=None):
            super().__init__(id, name)
            self.guild = guild or Guild()
         async def send(self, *args, **kwargs):
            m = MagicMock(spec=Message) 
            m.channel = self
            return m

    class Message(DiscordObject):
        def __init__(self, id=None, channel=None, author=None, content="", attachments=None, embeds=None):
            super().__init__(id)
            self.channel = channel or TextChannel()
            self.author = author or User()
            self.content = content
            self.attachments = attachments or []
            self.embeds = embeds or []
        async def add_reaction(self, emoji):
            pass

    class User(DiscordObject):
        def __init__(self, id=None, name=None, bot=False):
            super().__init__(id, name)
            self.bot = bot

    class ClientUser(User): 
        pass

    class Emoji(DiscordObject):
        pass
        
    class Embed: 
        def __init__(self, title=None, description=None, url=None, color=None):
            self.title = title
            self.description = description
            self.url = url
            self.color = color
            # Ensure image attribute and its url are MagicMocks for assertion capabilities
            self.image = MagicMock() 
            self.image.url = MagicMock()  # Make image.url a mock
            self.set_image = MagicMock() 

    class commands:
        class Bot:
            def __init__(self, command_prefix, intents):
                self.user = ClientUser(id=987654321, name="TestBot", bot=True) 
                self.guilds = []
                self.cogs = {}
            async def add_cog(self, cog, *, guild=None, guilds=None): 
                cog_name = cog.qualified_name if hasattr(cog, 'qualified_name') and callable(cog.qualified_name) else cog.__class__.__name__
                self.cogs[cog_name] = cog
            async def get_channel(self, channel_id):
                return TextChannel(id=channel_id)
            async def wait_until_ready(self):
                pass
            async def close(self):
                pass
            async def on_message(self, message): 
                pass

        class Cog:
            @classmethod
            def qualified_name(cls): 
                return cls.__name__
        
        class Context(DiscordObject): 
            def __init__(self, bot=None, message=None, channel=None, guild=None, author=None):
                self.bot = bot or commands.Bot("!", {})
                self.message = message or Message()
                self.channel = channel or TextChannel() 
                self.guild = guild or Guild()
                self.author = author or User()
                self.send = AsyncMock(return_value=MagicMock(spec=Message))

            async def send(self, *args, **kwargs):
                if self.channel:
                    return await self.channel.send(*args, **kwargs)
                m = MagicMock(spec=Message)
                return m
        
        Command = MagicMock 
        
        def command(*args, **kwargs): 
            def decorator(func):
                cmd_obj = commands.Command(func) 
                cmd_obj.callback = func 
                cmd_obj.name = func.__name__
                return cmd_obj
            return decorator

        class errors:
            class CommandNotFound(Exception):
                pass
    
    discord = MagicMock()
    discord.Intents.default = MagicMock(return_value=MagicMock(messages=True, typing=True, message_content=True))
    discord.Embed = Embed 
    discord.File = MagicMock(spec_set=True) 
    discord.TextChannel = TextChannel
    discord.Guild = Guild
    discord.User = User
    discord.ClientUser = ClientUser 
    discord.Message = Message
    discord.Emoji = Emoji
    discord.Forbidden = type('Forbidden', (Exception,), {}) 
    discord.HTTPException = type('HTTPException', (Exception,), {})
    discord.ext.commands = commands
    discord.ext.tasks = MagicMock()
    discord.ext.tasks.Loop = MagicMock 


from src.utils.RedditBot import RedditBotManager, CommandGroup
from src.utils.RedditMonitor import RedditMonitor 
from src.utils.SB_connector import SupabaseConnector 

@pytest.fixture
def mock_reddit_monitor():
    monitor = MagicMock(spec=RedditMonitor)
    monitor.initialize = AsyncMock()
    monitor.get_posts = AsyncMock()
    monitor.close = AsyncMock()
    monitor.processed_posts = set()
    monitor.post_content = {}
    return monitor

@pytest.fixture
def mock_supabase_connector():
    connector = MagicMock(spec=SupabaseConnector)
    connector.get_post_ids = MagicMock(return_value=["id1_from_db", "id2_from_db"])
    connector.database_ids = ["id1_from_db", "id2_from_db"] 
    connector.insert_entries = MagicMock() 
    return connector

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {
        "DISCORD_POST_CHANNEL": "1234567890",
        "CHECK_INTERVAL": "60",
        "SUBREDDIT_NAME": "testsub", 
        "TARGET_FLAIRS": "Flair1,Flair2",
        "REDDIT_CLIENT_ID": "test_client_id",
        "REDDIT_CLIENT_SECRET": "test_client_secret",
        "REDDIT_USER_AGENT": "test_user_agent",
        "REDDIT_USERNAME": "test_username",
        "REDDIT_PASSWORD": "test_password",
    }):
        yield

@pytest.fixture
def mock_guild():
    guild = MagicMock(spec=discord.Guild)
    guild.emojis = []
    guild.id = 123 
    guild.name = "Test Guild"
    return guild

@pytest.fixture
def mock_post_channel(mock_guild): 
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 1234567890 
    channel.name = "test-post-channel"
    channel.guild = mock_guild
    mock_sent_message = MagicMock(spec=discord.Message)
    mock_sent_message.channel = channel 
    channel.send = AsyncMock(return_value=mock_sent_message)
    return channel

@pytest.fixture
async def bot_manager(mock_env, mock_reddit_monitor, mock_supabase_connector, mock_post_channel):
    with patch('src.utils.RedditBot.RedditMonitor', return_value=mock_reddit_monitor), \
         patch('src.utils.RedditBot.SupabaseConnector', return_value=mock_supabase_connector), \
         patch('src.utils.RedditBot.logging'):
        with patch.object(discord.ext.commands.Bot, 'get_channel', return_value=mock_post_channel):
            manager = RedditBotManager(Supabase=True)
            manager.reddit_monitor = mock_reddit_monitor 
            manager.supabase = mock_supabase_connector
            
            manager.checknow_task = MagicMock(spec=discord.ext.tasks.Loop)
            manager.checknow_task.start = MagicMock()
            manager.checknow_task.stop = MagicMock()
            manager.checknow_task.change_interval = MagicMock()
            # Accessing the private mangled name directly is fragile.
            # Instead, the test should get the Loop object and then mock its `coro` attribute if needed
            # or the Loop object itself can be an AsyncMock if the SUT awaits `LoopName()`
            # For now, we assume the test will use `bot_manager.checknow_task.coro(bot_manager)`
            if hasattr(manager.checknow_task, '_coro'): # checknow_task is Loop instance
                 manager.checknow_task.coro = AsyncMock(wraps=manager.checknow_task._coro)
            else: # if checknow_task was replaced by a simple mock earlier
                 manager.checknow_task.coro = AsyncMock()


            manager.post_channel = mock_post_channel 
            manager.command_group = CommandGroup(manager.reddit_monitor, manager.supabase, manager.post_channel)
            yield manager


@pytest.fixture
def command_group(mock_reddit_monitor, mock_supabase_connector, mock_post_channel):
    group = CommandGroup(mock_reddit_monitor, mock_supabase_connector, mock_post_channel)
    group.published_posts = [] 
    return group


@pytest.fixture
def mock_ctx(bot_manager: RedditBotManager, mock_message: discord.Message, 
             mock_post_channel: discord.TextChannel, mock_guild: discord.Guild):
    ctx = MagicMock(spec=discord.ext.commands.Context)
    ctx.bot = bot_manager 
    ctx.message = mock_message
    ctx.channel = mock_post_channel 
    ctx.guild = mock_guild 
    ctx.author = mock_message.author
    ctx.send = AsyncMock(return_value=MagicMock(spec=discord.Message)) 
    return ctx


@pytest.fixture
def mock_message(mock_post_channel: discord.TextChannel): 
    message = MagicMock(spec=discord.Message)
    message.channel = mock_post_channel 
    message.author = MagicMock(spec=discord.User, bot=False, id=12345)
    message.content = "Test message"
    message.attachments = []
    message.embeds = []
    message.add_reaction = AsyncMock()
    message.id = 1122334455
    return message


# --- Test RedditBotManager ---

@pytest.mark.asyncio
async def test_bot_manager_init(mock_env): 
    with patch('src.utils.RedditBot.RedditMonitor') as MockedRedditMonitor, \
         patch('src.utils.RedditBot.SupabaseConnector') as MockedSupabaseConnector, \
         patch('src.utils.RedditBot.logging'), \
         patch.object(discord.ext.commands.Bot, 'get_channel'): 
        
        bot_sup = RedditBotManager(Supabase=True)
        MockedSupabaseConnector.assert_called_once()
        assert bot_sup.supabase is not None
        
        MockedSupabaseConnector.reset_mock()
        MockedRedditMonitor.reset_mock() 

        bot_no_sup = RedditBotManager(Supabase=False)
        MockedSupabaseConnector.assert_not_called()
        assert bot_no_sup.supabase is None

        assert MockedRedditMonitor.call_count == 1 
        assert bot_sup.reddit_monitor is not None
        assert bot_no_sup.reddit_monitor is not None
        
        assert bot_sup.post_channel == 1234567890 
        assert bot_sup.check_interval == 60

@pytest.mark.asyncio
async def test_bot_manager_on_ready(bot_manager: RedditBotManager, mock_reddit_monitor, mock_post_channel):
    bot_manager.add_cog = AsyncMock() 
    bot_manager.command_group = None 
    
    await bot_manager.on_ready()

    assert bot_manager.post_channel == mock_post_channel 

    bot_manager.add_cog.assert_called_once()
    added_cog = bot_manager.add_cog.call_args[0][0]
    assert isinstance(added_cog, CommandGroup)
    assert added_cog.reddit_monitor == mock_reddit_monitor
    assert added_cog.supabase == bot_manager.supabase 
    assert added_cog.authorised_channel == mock_post_channel

    mock_reddit_monitor.initialize.assert_called_once()
    
    assert bot_manager.auto_post is True 
    bot_manager.checknow_task.change_interval.assert_called_once_with(seconds=bot_manager.check_interval)
    bot_manager.checknow_task.start.assert_called_once()


@pytest.mark.asyncio
async def test_bot_manager_on_message_ignore_self(bot_manager: RedditBotManager, mock_message: discord.Message):
    mock_message.author = bot_manager.user 
    assert bot_manager.command_group is not None
    bot_manager.command_group.get_emoji_by_name = AsyncMock() 

    with patch.object(discord.ext.commands.Bot, 'on_message', new_callable=AsyncMock) as mock_super_on_message:
        await bot_manager.on_message(mock_message)
    
    bot_manager.command_group.get_emoji_by_name.assert_not_called()
    # If message.author == self.user, the SUT's on_message returns early before super().on_message.
    mock_super_on_message.assert_not_called()


@pytest.mark.asyncio
async def test_bot_manager_on_message_ignore_other_channel(bot_manager: RedditBotManager, mock_message: discord.Message, mock_post_channel: discord.TextChannel):
    other_channel = MagicMock(spec=discord.TextChannel, id=11111) 
    mock_message.channel = other_channel
    
    bot_manager.post_channel = mock_post_channel 
    assert bot_manager.command_group is not None
    bot_manager.command_group.get_emoji_by_name = AsyncMock()

    with patch.object(discord.ext.commands.Bot, 'on_message', new_callable=AsyncMock) as mock_super_on_message:
        await bot_manager.on_message(mock_message)

    bot_manager.command_group.get_emoji_by_name.assert_not_called()
    mock_super_on_message.assert_called_once_with(mock_message)

@pytest.mark.asyncio
async def test_bot_manager_on_message_add_reactions(bot_manager: RedditBotManager, mock_message: discord.Message, mock_post_channel: discord.TextChannel):
    bot_manager.post_channel = mock_post_channel 
    mock_message.channel = mock_post_channel
    mock_message.attachments = [MagicMock()] 
    mock_message.embeds = [] 
    mock_message.content = "No gif here" 
    
    mock_emoji_obj = MagicMock(spec=discord.Emoji)
    
    assert bot_manager.command_group is not None
    bot_manager.command_group.get_emoji_by_name = AsyncMock(return_value=mock_emoji_obj)
    bot_manager.command_group.add_reactions_to_message = AsyncMock()
        
    with patch.object(discord.ext.commands.Bot, 'on_message', new_callable=AsyncMock) as mock_super_on_message:
        await bot_manager.on_message(mock_message)

    expected_emoji_names = ["rate_0", "CherryTomato", "GreenPepper", "YellowPepper", "CarolinaReaper", "FIRE"]
    assert bot_manager.command_group.get_emoji_by_name.call_count == len(expected_emoji_names) 
    for name in expected_emoji_names:
        bot_manager.command_group.get_emoji_by_name.assert_any_call(mock_post_channel, name) 
    
    bot_manager.command_group.add_reactions_to_message.assert_called_once_with(
        mock_message, [mock_emoji_obj] * len(expected_emoji_names)
    )
    mock_super_on_message.assert_called_once_with(mock_message)


@pytest.mark.asyncio
async def test_bot_manager_on_message_no_reaction_for_gif_in_embed_url(bot_manager: RedditBotManager, mock_message: discord.Message, mock_post_channel: discord.TextChannel):
    bot_manager.post_channel = mock_post_channel
    mock_message.channel = mock_post_channel
    # Ensure the dummy Embed has a 'url' attribute that can be checked
    gif_embed = discord.Embed() 
    gif_embed.url = "http://giphy.com/some.gif" 
    gif_embed.image = None # Ensure image part of embed doesn't trigger if only URL is for GIF
    mock_message.embeds = [gif_embed]
    mock_message.attachments = []
    mock_message.content = "non-gif content"
    
    assert bot_manager.command_group is not None
    bot_manager.command_group.get_emoji_by_name = AsyncMock()
    bot_manager.command_group.add_reactions_to_message = AsyncMock()
    
    with patch.object(discord.ext.commands.Bot, 'on_message', new_callable=AsyncMock) as mock_super_on_message:
        await bot_manager.on_message(mock_message)

    bot_manager.command_group.get_emoji_by_name.assert_not_called()
    bot_manager.command_group.add_reactions_to_message.assert_not_called()
    mock_super_on_message.assert_called_once_with(mock_message)

@pytest.mark.asyncio
async def test_bot_manager_on_message_no_reaction_for_gif_in_content(bot_manager: RedditBotManager, mock_message: discord.Message, mock_post_channel: discord.TextChannel):
    bot_manager.post_channel = mock_post_channel
    mock_message.channel = mock_post_channel
    mock_message.content = "this is a gif http://example.com/image.gif" 
    mock_message.attachments = [MagicMock()] 
    mock_message.embeds = []

    assert bot_manager.command_group is not None
    bot_manager.command_group.get_emoji_by_name = AsyncMock()
    bot_manager.command_group.add_reactions_to_message = AsyncMock()

    with patch.object(discord.ext.commands.Bot, 'on_message', new_callable=AsyncMock) as mock_super_on_message:
        await bot_manager.on_message(mock_message)

    bot_manager.command_group.get_emoji_by_name.assert_not_called()
    bot_manager.command_group.add_reactions_to_message.assert_not_called()
    mock_super_on_message.assert_called_once_with(mock_message)


@pytest.mark.asyncio
async def test_bot_manager_checknow_task_call(bot_manager: RedditBotManager, mock_post_channel: discord.TextChannel):
    bot_manager.post_channel = mock_post_channel 
    assert bot_manager.command_group is not None
    bot_manager.command_group.execute_checknow = AsyncMock()
    
    # Call the .coro attribute of the Loop mock, passing the bot_manager instance
    # This assumes checknow_task.coro is an AsyncMock (as set in fixture)
    await bot_manager.checknow_task.coro(bot_manager) 
    
    bot_manager.command_group.execute_checknow.assert_called_once_with(mock_post_channel)


@pytest.mark.asyncio
async def test_bot_manager_checknow_task_no_channel_call(bot_manager: RedditBotManager):
    bot_manager.post_channel = None 
    assert bot_manager.command_group is not None
    bot_manager.command_group.execute_checknow = AsyncMock()

    with patch('src.utils.RedditBot.logging') as mock_logging:
        await bot_manager.checknow_task.coro(bot_manager) # Call the .coro
    
    bot_manager.command_group.execute_checknow.assert_not_called()
    mock_logging.warning.assert_called_with("Post channel not found for checknow task.")


@pytest.mark.asyncio
async def test_bot_manager_close(bot_manager: RedditBotManager, mock_reddit_monitor: MagicMock):
    with patch.object(discord.ext.commands.Bot, 'close', new_callable=AsyncMock) as mock_super_close:
        await bot_manager.close()

    bot_manager.checknow_task.stop.assert_called_once()
    mock_reddit_monitor.close.assert_called_once()
    mock_super_close.assert_called_once()


# --- Test CommandGroup ---

@pytest.mark.asyncio
async def test_command_group_hello(command_group: CommandGroup, mock_ctx: MagicMock):
    await command_group.hello.callback(command_group, mock_ctx)
    mock_ctx.send.assert_called_once_with("Hello I am a bot.")

@pytest.mark.asyncio
async def test_command_group_get_emoji_by_name_found(command_group: CommandGroup, mock_ctx: MagicMock, mock_guild: MagicMock):
    mock_emoji = MagicMock(spec=discord.Emoji)
    mock_emoji.name = "test_emoji"
    mock_guild.emojis = [mock_emoji]
    mock_ctx.guild = mock_guild

    emoji = await command_group.get_emoji_by_name(mock_ctx, "test_emoji")
    assert emoji == mock_emoji

@pytest.mark.asyncio
async def test_command_group_get_emoji_by_name_not_found(command_group: CommandGroup, mock_ctx: MagicMock, mock_guild: MagicMock):
    mock_guild.emojis = [] 
    mock_ctx.guild = mock_guild
    
    with patch('src.utils.RedditBot.logging') as mock_logging:
        emoji = await command_group.get_emoji_by_name(mock_ctx, "non_existent_emoji")
    
    assert emoji is None
    mock_logging.warning.assert_called_with(f"Emoji 'non_existent_emoji' not found in guild '{mock_guild.name if mock_guild else 'N/A'}'.")

@pytest.mark.asyncio
async def test_command_group_get_local_ids_file_exists(command_group: CommandGroup):
    command_group.supabase = None 
    
    mock_csv_data = "id,title,author\npost1,Title1,Author1\npost2,Title2,Author2\n"
    m_open = mock_open(read_data=mock_csv_data)
    
    with patch('os.path.exists', return_value=True) as mock_path_exists, \
         patch('builtins.open', m_open) as mock_open_call:
        ids = command_group._get_local_ids()
        
    assert ids == ["post1", "post2"]
    mock_path_exists.assert_called_once_with("posted_ids.csv")
    mock_open_call.assert_called_once_with("posted_ids.csv", mode="r", newline="", encoding="utf-8")


@pytest.mark.asyncio
async def test_command_group_get_local_ids_file_not_found(command_group: CommandGroup):
    command_group.supabase = None 
    with patch('os.path.exists', return_value=False) as mock_path_exists:
        ids = command_group._get_local_ids()
    assert ids == []
    mock_path_exists.assert_called_once_with("posted_ids.csv")


@pytest.mark.asyncio
async def test_command_group_init_with_supabase(mock_reddit_monitor, mock_supabase_connector, mock_post_channel):
    mock_supabase_connector.database_ids = ["db_id1", "db_id2"]
    def mock_command_decorator(*args, **kwargs): 
        def decorator(func):
            cmd_obj = MagicMock(spec=discord.ext.commands.Command); cmd_obj.callback = func
            return cmd_obj
        return decorator
    with patch('discord.ext.commands.command', mock_command_decorator):
        group = CommandGroup(mock_reddit_monitor, mock_supabase_connector, mock_post_channel)
    assert group.posted_ids == ["db_id1", "db_id2"]

@pytest.mark.asyncio
async def test_command_group_init_without_supabase(mock_reddit_monitor, mock_post_channel):
    def mock_command_decorator(*args, **kwargs): 
        def decorator(func):
            cmd_obj = MagicMock(spec=discord.ext.commands.Command); cmd_obj.callback = func
            return cmd_obj
        return decorator
    with patch('src.utils.RedditBot.CommandGroup._get_local_ids', return_value=["local_id1"]) as mock_get_local, \
         patch('discord.ext.commands.command', mock_command_decorator):
        group = CommandGroup(mock_reddit_monitor, None, mock_post_channel)
        assert group.supabase is None
        mock_get_local.assert_called_once()
        assert group.posted_ids == ["local_id1"]

@pytest.mark.asyncio
async def test_command_group_checknow_unauthorized_channel(command_group: CommandGroup, mock_ctx: MagicMock):
    command_group.authorised_channel = MagicMock(spec=discord.TextChannel, id=99999)
    mock_ctx.channel.id = 11111 
    command_group.execute_checknow = AsyncMock()
    await command_group.checknow.callback(command_group, mock_ctx)
    mock_ctx.send.assert_called_once_with("Im not authorized to publish in this channel")
    command_group.execute_checknow.assert_not_called()

@pytest.mark.asyncio
async def test_command_group_checknow_authorized_channel(command_group: CommandGroup, mock_ctx: MagicMock, mock_post_channel: discord.TextChannel):
    command_group.authorised_channel = mock_post_channel
    mock_ctx.channel = mock_post_channel
    command_group.execute_checknow = AsyncMock()
    await command_group.checknow.callback(command_group, mock_ctx)
    command_group.execute_checknow.assert_called_once_with(mock_ctx)

@pytest.mark.asyncio
async def test_command_group_execute_checknow_no_new_content(command_group: CommandGroup, mock_ctx: MagicMock, mock_reddit_monitor: MagicMock):
    mock_reddit_monitor.post_content = {} 
    command_group.publish_content = AsyncMock()
    await command_group.execute_checknow(mock_ctx)
    mock_ctx.send.assert_any_call("Checking for new posts...")
    mock_reddit_monitor.get_posts.assert_called_once()
    mock_ctx.send.assert_any_call("No new content to process.")
    command_group.publish_content.assert_not_called()

@pytest.mark.asyncio
async def test_command_group_execute_checknow_with_new_content(command_group: CommandGroup, mock_ctx: MagicMock, mock_reddit_monitor: MagicMock, mock_supabase_connector: MagicMock):
    mock_reddit_monitor.post_content = {"new_post1": "content1", "already_posted_id": "content2"}
    command_group.posted_ids = ["already_posted_id"]
    command_group.publish_content = AsyncMock()
    command_group.supabase = mock_supabase_connector 
    await command_group.execute_checknow(mock_ctx)
    mock_ctx.send.assert_any_call("Checking for new posts...")
    mock_reddit_monitor.get_posts.assert_called_once()
    expected_content_to_publish = {"new_post1": "content1"}
    command_group.publish_content.assert_called_once_with(expected_content_to_publish, mock_ctx)
    if command_group.supabase:
        mock_supabase_connector.get_post_ids.assert_called_once()

@pytest.mark.asyncio
async def test_command_group_create_post_embed_valid(command_group: CommandGroup):
    parsed_content = {"Title": "Test Title", "Author": "Test Author", "Link": "http://example.com/link"}
    embed = await command_group._create_post_embed(parsed_content)
    assert isinstance(embed, discord.Embed)
    assert embed.title == "Test Title"
    assert embed.description == "New post by Test Author"
    assert embed.url == "http://example.com/link"
    assert embed.image.url == "http://example.com/link"
    parsed_gallery_content = {"Title": "Gallery Title", "Author": "Gallery Author", "Link": "http://example.com/gallery", "Images": ["img1.jpg"]}
    gallery_embed = await command_group._create_post_embed(parsed_gallery_content, is_gallery=True)
    assert isinstance(gallery_embed, discord.Embed)
    assert gallery_embed.title == "Gallery Title"

@pytest.mark.asyncio
async def test_command_group_create_post_embed_missing_keys(command_group: CommandGroup):
    with patch('src.utils.RedditBot.logging') as mock_logging:
        parsed_content_missing = {"Title": "Test Title"}
        embed = await command_group._create_post_embed(parsed_content_missing)
        assert embed is None
        mock_logging.error.assert_called()

@pytest.mark.asyncio
async def test_command_group_publish_content_simple_post(command_group: CommandGroup, mock_ctx: MagicMock, mock_post_channel: discord.TextChannel):
    post_content_dict = {"post123": "Raw content string for post123"}
    parsed_content = {"Title": "Test Post 123", "Author": "Author X", "Link": "http://example.com/post123"}
    mock_embed_obj = discord.Embed(title="Test Embed") 
    command_group.parse_reddit_post = AsyncMock(return_value=parsed_content)
    command_group._create_post_embed = AsyncMock(return_value=mock_embed_obj)
    mock_emoji = MagicMock(spec=discord.Emoji)
    command_group.get_emoji_by_name = AsyncMock(return_value=mock_emoji)
    command_group.add_reactions_to_message = AsyncMock()
    command_group.update_posted_ids = MagicMock()
    mock_ctx.channel = mock_post_channel 
    if command_group.supabase:
        command_group.supabase.insert_entries = MagicMock()
    
    command_group.published_posts = [] 

    await command_group.publish_content(post_content_dict, mock_ctx)

    command_group.parse_reddit_post.assert_called_once_with("Raw content string for post123")
    command_group._create_post_embed.assert_called_once_with(parsed_content)
    mock_post_channel.send.assert_called_once_with(embed=mock_embed_obj)
    sent_message_mock = mock_post_channel.send.return_value
    command_group.add_reactions_to_message.assert_called_once()
    assert command_group.add_reactions_to_message.call_args[0][0] == sent_message_mock
    emoji_list_arg = command_group.add_reactions_to_message.call_args[0][1]
    assert len(emoji_list_arg) == len(["rate_0", "CherryTomato", "GreenPepper", "YellowPepper", "CarolinaReaper", "FIRE"])
    assert all(e == mock_emoji for e in emoji_list_arg)
    
    expected_published_post = {"id": "post123", "title": "Test Post 123", "author": "Author X"}
    # Check the argument to insert_entries if supabase is active
    if command_group.supabase:
        command_group.supabase.insert_entries.assert_called_once_with([expected_published_post])
    else:
        # If no supabase, check that update_posted_ids was called and published_posts contains the item
        command_group.update_posted_ids.assert_called_once()
        assert expected_published_post in command_group.published_posts


@pytest.mark.asyncio
async def test_command_group_publish_content_gallery_post(command_group: CommandGroup, mock_ctx: MagicMock, mock_post_channel: discord.TextChannel):
    post_content_dict = {"gallery01": "Raw gallery content"}
    parsed_content = {
        "Title": "Gallery Fun", "Author": "Picasso", "Link": "http://example.com/gallery01",
        "Images": ["http://img1.png", "http://img2.png"] 
    }
    mock_embed_obj = discord.Embed(title="Gallery Embed") 
    mock_discord_file = MagicMock(spec=discord.File) 
    command_group.parse_reddit_post = AsyncMock(return_value=parsed_content)
    command_group._create_post_embed = AsyncMock(return_value=mock_embed_obj)
    command_group.get_emoji_by_name = AsyncMock(return_value=MagicMock(spec=discord.Emoji))
    command_group.add_reactions_to_message = AsyncMock()
    mock_ctx.channel = mock_post_channel
    
    command_group.published_posts = []

    with patch('src.utils.RedditBot.mosaic_maker', AsyncMock(return_value=BytesIO(b"fake image data"))) as mock_mosaic_maker, \
         patch('discord.File', return_value=mock_discord_file) as MockedDiscordFile: 
        await command_group.publish_content(post_content_dict, mock_ctx)
    command_group.parse_reddit_post.assert_called_once_with("Raw gallery content")
    command_group._create_post_embed.assert_called_once_with(parsed_content, is_gallery=True)
    mock_mosaic_maker.assert_called_once_with(["http://img1.png", "http://img2.png"])
    MockedDiscordFile.assert_called_once_with(mock_mosaic_maker.return_value, filename="combined.png")
    mock_post_channel.send.assert_called_once_with(embed=mock_embed_obj, file=mock_discord_file)
    mock_embed_obj.set_image.assert_called_once_with(url="attachment://combined.png") 
    expected_published_post = {"id": "gallery01", "title": "Gallery Fun", "author": "Picasso"}
    if command_group.supabase:
        command_group.supabase.insert_entries.assert_called_once_with([expected_published_post])


@pytest.mark.asyncio
async def test_command_group_publish_content_skip_posted_id(command_group: CommandGroup, mock_ctx: MagicMock):
    command_group.posted_ids = ["existing_post"]
    post_content_dict = {"existing_post": "some content"}
    command_group.parse_reddit_post = AsyncMock() 
    with patch('src.utils.RedditBot.logging') as mock_logging:
        await command_group.publish_content(post_content_dict, mock_ctx)
    mock_logging.info.assert_any_call("Post ID existing_post already published. Skipping.")
    command_group.parse_reddit_post.assert_not_called()
    mock_ctx.channel.send.assert_not_called()

@pytest.mark.asyncio
async def test_command_group_publish_content_send_forbidden(command_group: CommandGroup, mock_ctx: MagicMock, mock_post_channel: discord.TextChannel):
    post_content_dict = {"new_post": "content"}
    parsed_content = {"Title": "A Title", "Author": "An Author", "Link": "http://link.com"}
    mock_embed_obj = discord.Embed(title="Embed")
    command_group.parse_reddit_post = AsyncMock(return_value=parsed_content)
    command_group._create_post_embed = AsyncMock(return_value=mock_embed_obj)
    mock_ctx.channel = mock_post_channel
    mock_post_channel.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "cannot send"))
    with patch('src.utils.RedditBot.logging') as mock_logging:
        await command_group.publish_content(post_content_dict, mock_ctx)
    mock_logging.error.assert_any_call(
        f"Bot lacks permissions to send messages in channel {mock_post_channel.name} ({mock_post_channel.id}). Post ID: new_post"
    )
    assert not any(p['id'] == 'new_post' for p in command_group.published_posts)

@pytest.mark.asyncio
async def test_command_group_parse_reddit_post(command_group: CommandGroup):
    content_str = "**Title** Test Title **Author** Test Author **Link** http://example.com **IMAGES** url1 url2"
    parsed = await command_group.parse_reddit_post(content_str)
    assert parsed == {
        "Title": "Test Title", "Author": "Test Author", "Link": "http://example.com", "IMAGES": ["url1", "url2"] 
    }
    content_no_images = "**Title** No Image Title **Author** Author B **Link** http://another.com"
    parsed_no_images = await command_group.parse_reddit_post(content_no_images)
    assert parsed_no_images == {"Title": "No Image Title", "Author": "Author B", "Link": "http://another.com"}
    assert "IMAGES" not in parsed_no_images

@pytest.mark.asyncio
async def test_command_group_add_reactions_to_message_errors(command_group: CommandGroup, mock_message: discord.Message):
    mock_emoji1 = MagicMock(spec=discord.Emoji, name="emoji1")
    mock_emoji2 = MagicMock(spec=discord.Emoji, name="emoji2") 
    mock_emoji3 = MagicMock(spec=discord.Emoji, name="emoji3") 
    mock_message.add_reaction = AsyncMock()
    async def reaction_side_effect(emoji):
        if emoji.name == "emoji2": raise discord.Forbidden(MagicMock(), "Reaction forbidden")
        if emoji.name == "emoji3": raise discord.HTTPException(MagicMock(), "Reaction HTTP error")
    mock_message.add_reaction.side_effect = reaction_side_effect
    emoji_list = [mock_emoji1, mock_emoji2, mock_emoji3]
    with patch('src.utils.RedditBot.logging') as mock_logging:
        await command_group.add_reactions_to_message(mock_message, emoji_list)
    mock_message.add_reaction.assert_any_call(mock_emoji1)
    mock_message.add_reaction.assert_any_call(mock_emoji2)
    assert mock_message.add_reaction.call_count == 2 
    mock_logging.error.assert_any_call(
        f"Bot lacks permissions to add reactions in channel {mock_message.channel.name} ({mock_message.channel.id}). Emoji: emoji2"
    )
    http_error_logged = any(
        call_args[0].startswith("Failed to add reaction emoji3") for call_args in mock_logging.warning.call_args_list
    )
    assert not http_error_logged

@pytest.mark.asyncio
async def test_command_group_update_posted_ids_new_file(command_group: CommandGroup):
    command_group.supabase = None 
    command_group.published_posts = [{"id": "p1", "title": "T1", "author": "A1"}, {"id": "p2", "title": "T2", "author": "A2"}]
    command_group.posted_ids = [] 
    mock_csv_writer_instance = MagicMock()
    m_open = mock_open() 
    
    with patch('os.path.exists', return_value=False) as mock_path_exists, \
         patch('builtins.open', m_open) as mock_open_call, \
         patch('csv.DictWriter', return_value=mock_csv_writer_instance) as mock_csv_dict_writer:
        command_group.update_posted_ids()

    mock_path_exists.assert_called_once_with("posted_ids.csv")
    mock_open_call.assert_called_once_with("posted_ids.csv", mode="w", newline="", encoding="utf-8")
    mock_csv_dict_writer.assert_called_once_with(m_open.return_value, fieldnames=["id", "title", "author"])
    
    mock_csv_writer_instance.writeheader.assert_called_once()
    assert mock_csv_writer_instance.writerow.call_count == 2
    mock_csv_writer_instance.writerow.assert_any_call({"id": "p1", "title": "T1", "author": "A1"})
    mock_csv_writer_instance.writerow.assert_any_call({"id": "p2", "title": "T2", "author": "A2"})
    assert "p1" in command_group.posted_ids
    assert "p2" in command_group.posted_ids

@pytest.mark.asyncio
async def test_command_group_update_posted_ids_append_file(command_group: CommandGroup):
    command_group.supabase = None
    command_group.published_posts = [{"id": "p3", "title": "T3", "author": "A3"}]
    command_group.posted_ids = ["p1", "p2"] 
    mock_csv_writer_instance = MagicMock()
    m_open = mock_open()

    with patch('os.path.exists', return_value=True) as mock_path_exists, \
         patch('builtins.open', m_open) as mock_open_call, \
         patch('csv.DictWriter', return_value=mock_csv_writer_instance) as mock_csv_dict_writer:
        command_group.update_posted_ids()
        
    mock_path_exists.assert_called_once_with("posted_ids.csv")
    mock_open_call.assert_called_once_with("posted_ids.csv", mode="a", newline="", encoding="utf-8")
    mock_csv_dict_writer.assert_called_once_with(m_open.return_value, fieldnames=["id", "title", "author"])
    mock_csv_writer_instance.writeheader.assert_not_called() 
    mock_csv_writer_instance.writerow.assert_called_once_with({"id": "p3", "title": "T3", "author": "A3"})
    assert "p3" in command_group.posted_ids
    assert "p1" in command_group.posted_ids 
    assert "p2" in command_group.posted_ids
```

[end of tests/test_reddit_bot.py]
