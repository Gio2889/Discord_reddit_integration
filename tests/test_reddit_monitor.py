import pytest
import asyncio
import sys 
import os
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.RedditMonitor import RedditMonitor
from prawcore.exceptions import RequestException, ResponseException, OAuthException
from asyncpraw.exceptions import InvalidURL
from PIL import UnidentifiedImageError 
import aiofiles 
# No need to import aiohttp directly in the test file if we patch it where it's used in SUT

# --- Fixtures ---

@pytest.fixture
def mock_env_vars():
    with patch.dict(os.environ, {
        "SUBREDDIT_NAME": "testsub1,testsub2",
        "TARGET_FLAIRS": "FlairA,FlairB",
        "REDDIT_CLIENT_ID": "test_id",
        "REDDIT_CLIENT_SECRET": "test_secret",
        "REDDIT_USER_AGENT": "test_agent",
        "REDDIT_USERNAME": "test_user", 
        "REDDIT_PASSWORD": "test_pass",
    }) as patched_env:
        yield patched_env

@pytest.fixture
def reddit_monitor_instance(mock_env_vars):
    with patch.object(RedditMonitor, 'load_processed_posts', MagicMock(return_value=None)):
        monitor = RedditMonitor()
        monitor.processed_posts = set() 
        monitor.post_content = {}     
        yield monitor


@pytest.fixture
def mock_submission():
    submission = AsyncMock()
    submission.id = "test_submission_id"
    submission.title = "Test Submission Title"
    author_mock = AsyncMock() 
    author_mock.name = "TestAuthor" 
    submission.author = author_mock 
    submission.url = "http://reddit.com/test_submission"
    submission.is_self = False
    submission.is_gallery = False
    submission.is_video = False
    submission.selftext = "This is a test text post."
    submission.gallery_data = None
    submission.media_metadata = None
    submission.load = AsyncMock() 
    return submission

class AsyncIterator: 
    def __init__(self, items):
        self.items = items
        self.idx = 0
    def __aiter__(self):
        return self
    async def __anext__(self):
        if self.idx < len(self.items):
            res = self.items[self.idx]
            self.idx += 1
            return res
        else:
            raise StopAsyncIteration

# --- Test Cases ---

def test_reddit_monitor_init_no_flairs(mock_env_vars):
    with patch.dict(os.environ, {"TARGET_FLAIRS": ""}), \
         patch.object(RedditMonitor, 'load_processed_posts', MagicMock()): 
        monitor = RedditMonitor()
        assert monitor.subreddit_names == "testsub1,testsub2"
        assert monitor.target_flairs == ""
        assert monitor.flair_query is None 
        assert monitor.max_retries == 3
        monitor.load_processed_posts.assert_called_once()

def test_reddit_monitor_init_with_flairs(mock_env_vars): 
    with patch.object(RedditMonitor, 'load_processed_posts', MagicMock()):
        monitor = RedditMonitor() 
        assert monitor.target_flairs == "FlairA,FlairB"
        expected_query = '(flair:"FlairA" OR flair:"FlairB")'
        assert monitor.flair_query == expected_query

def test_build_flair_query(reddit_monitor_instance: RedditMonitor): 
    assert reddit_monitor_instance._build_flair_query(None) is None
    assert reddit_monitor_instance._build_flair_query("") is None
    assert reddit_monitor_instance._build_flair_query("Funny") == 'flair:"Funny"'
    assert reddit_monitor_instance._build_flair_query("Funny,Serious") == '(flair:"Funny" OR flair:"Serious")'
    assert reddit_monitor_instance._build_flair_query("  Funny  ,  Serious  ") == '(flair:"Funny" OR flair:"Serious")'


@pytest.mark.asyncio
async def test_initialize_reddit_session(reddit_monitor_instance: RedditMonitor, mock_env_vars):
    # Patch ClientSession in the module where RedditMonitor looks it up
    with patch('src.utils.RedditMonitor.asyncpraw.Reddit', new_callable=MagicMock) as mock_praw_reddit, \
         patch('src.utils.RedditMonitor.ClientSession', new_callable=MagicMock) as mock_aiohttp_client_session_in_sut:
        
        mock_session_obj = AsyncMock() 
        mock_aiohttp_client_session_in_sut.return_value = mock_session_obj 
        mock_reddit_instance = AsyncMock()
        mock_praw_reddit.return_value = mock_reddit_instance

        await reddit_monitor_instance.initialize()

        mock_aiohttp_client_session_in_sut.assert_called_once_with(trust_env=True)
        mock_praw_reddit.assert_called_once_with(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="test_agent",
            username="test_user", 
            password="test_pass",
            requestor_kwargs={"session": mock_session_obj},
        )
        assert reddit_monitor_instance.session == mock_session_obj
        assert reddit_monitor_instance.reddit == mock_reddit_instance


def test_load_processed_posts_file_found(): 
    with patch.dict(os.environ, { 
        "SUBREDDIT_NAME": "test", "TARGET_FLAIRS": "",
        "REDDIT_CLIENT_ID": "test", "REDDIT_CLIENT_SECRET": "test",
        "REDDIT_USER_AGENT": "test", "REDDIT_USERNAME": "test", "REDDIT_PASSWORD": "test"
    }):
        monitor = RedditMonitor() 
    mock_file_content = "id1\nid2\nid3\n"
    m_open = mock_open(read_data=mock_file_content)
    with patch('builtins.open', m_open), \
         patch('os.path.exists', return_value=True), \
         patch('logging.info') as mock_log_info:
        monitor.load_processed_posts() 
    assert monitor.processed_posts == {"id1", "id2", "id3"}
    m_open.assert_called_once_with("processed_posts.txt", "r")
    mock_log_info.assert_any_call(f"Loaded {len(monitor.processed_posts)} processed post IDs from processed_posts.txt.")


def test_load_processed_posts_file_not_found(): 
    with patch.dict(os.environ, {
        "SUBREDDIT_NAME": "test", "TARGET_FLAIRS": "",
        "REDDIT_CLIENT_ID": "test", "REDDIT_CLIENT_SECRET": "test",
        "REDDIT_USER_AGENT": "test", "REDDIT_USERNAME": "test", "REDDIT_PASSWORD": "test"
    }):
        monitor = RedditMonitor()
    with patch('os.path.exists', return_value=False), \
         patch('logging.info') as mock_log_info: 
        monitor.load_processed_posts()
    assert monitor.processed_posts == set() 
    mock_log_info.assert_called_once_with("processed_posts.txt not found. Starting with an empty set of processed posts.")

def test_load_processed_posts_other_exception():
    with patch.dict(os.environ, {
        "SUBREDDIT_NAME": "test", "TARGET_FLAIRS": "",
        "REDDIT_CLIENT_ID": "test", "REDDIT_CLIENT_SECRET": "test",
        "REDDIT_USER_AGENT": "test", "REDDIT_USERNAME": "test", "REDDIT_PASSWORD": "test"
    }):
        monitor = RedditMonitor() 
    m_open = mock_open()
    m_open.side_effect = Exception("Test read error")
    with patch('builtins.open', m_open), \
         patch('os.path.exists', return_value=True), \
         patch('logging.error') as mock_log_error: 
        monitor.load_processed_posts()
    assert monitor.processed_posts == set() 
    mock_log_error.assert_called_once()
    assert "Error loading processed posts: Test read error" in mock_log_error.call_args[0][0]


@pytest.mark.asyncio
async def test_save_processed_posts_success(reddit_monitor_instance: RedditMonitor):
    reddit_monitor_instance.processed_posts = {"idA", "idB"}
    mock_async_file = AsyncMock()
    mock_async_file.writelines = AsyncMock() 

    async_context_manager_mock = AsyncMock()
    async_context_manager_mock.__aenter__.return_value = mock_async_file

    with patch('src.utils.RedditMonitor.aiofiles.open', return_value=async_context_manager_mock) as mock_aio_open, \
         patch('logging.info') as mock_log_info:
        await reddit_monitor_instance.save_processed_posts()

    mock_aio_open.assert_called_once_with("processed_posts.txt", "w")
    mock_async_file.writelines.assert_called_once()
    written_content_generator = mock_async_file.writelines.call_args[0][0]
    written_lines = sorted(list(written_content_generator))
    assert written_lines == sorted(["idA\n", "idB\n"])
    mock_log_info.assert_any_call("Successfully saved processed posts to processed_posts.txt.")


@pytest.mark.asyncio
async def test_save_processed_posts_exception(reddit_monitor_instance: RedditMonitor):
    reddit_monitor_instance.processed_posts = {"idC"}
    with patch('src.utils.RedditMonitor.aiofiles.open', side_effect=Exception("Failed to write")), \
         patch('logging.error') as mock_log_error:
        await reddit_monitor_instance.save_processed_posts()
    mock_log_error.assert_called_once()
    assert "Error saving processed posts: Failed to write" in mock_log_error.call_args[0][0]


@pytest.mark.asyncio
async def test_get_post_content_text_post(reddit_monitor_instance: RedditMonitor, mock_submission: MagicMock):
    mock_submission.is_self = True
    content = await reddit_monitor_instance.get_post_content(mock_submission)
    assert "**Title** Test Submission Title" in content
    assert "**Author** TestAuthor" in content
    assert "**Text** This is a test text post." in content
    mock_submission.load.assert_called_once()

@pytest.mark.asyncio
async def test_get_post_content_link_post(reddit_monitor_instance: RedditMonitor, mock_submission: MagicMock):
    content = await reddit_monitor_instance.get_post_content(mock_submission)
    assert "**Title** Test Submission Title" in content
    assert "**Author** TestAuthor" in content
    assert f"**Link** {mock_submission.url}" in content
    mock_submission.load.assert_called_once()

@pytest.mark.asyncio
async def test_get_post_content_video_post(reddit_monitor_instance: RedditMonitor, mock_submission: MagicMock):
    mock_submission.is_video = True
    with patch('logging.info') as mock_log_info:
        content = await reddit_monitor_instance.get_post_content(mock_submission)
    assert content is None
    mock_log_info.assert_called_with(f"Post {mock_submission.id} is a video. Skipping content generation as per policy.")
    mock_submission.load.assert_called_once()


@pytest.mark.asyncio
async def test_get_post_content_gallery_post_valid(reddit_monitor_instance: RedditMonitor, mock_submission: MagicMock):
    mock_submission.is_gallery = True
    mock_submission.gallery_data = {
        "items": [{"media_id": "media1"}, {"media_id": "media2"}]
    }
    mock_submission.media_metadata = {
        "media1": {"s": {"u": "http://example.com/img1.jpg"}},
        "media2": {"s": {"gif": "http://example.com/img2.gif"}} 
    }
    content = await reddit_monitor_instance.get_post_content(mock_submission)
    assert "**Title** Test Submission Title" in content
    assert f"**Link** {mock_submission.url}" in content 
    assert "**Images** http://example.com/img1.jpg http://example.com/img2.gif" in content
    mock_submission.load.assert_called_once()


@pytest.mark.asyncio
async def test_get_post_content_gallery_post_missing_metadata(reddit_monitor_instance: RedditMonitor, mock_submission: MagicMock):
    mock_submission.is_gallery = True
    mock_submission.gallery_data = {"items": [{"media_id": "media1"}]}
    mock_submission.media_metadata = {} 
    with patch('logging.warning') as mock_log_warning:
        content = await reddit_monitor_instance.get_post_content(mock_submission)
    assert "**Images**" not in content 
    assert f"**Link** {mock_submission.url}" in content 
    mock_log_warning.assert_any_call(f"Media ID media1 not found in media_metadata for gallery post {mock_submission.id}.")
    mock_log_warning.assert_any_call(f"Gallery post {mock_submission.id} had no processable images.")


@pytest.mark.asyncio
async def test_get_post_content_attribute_error_handled(reddit_monitor_instance: RedditMonitor, mock_submission: MagicMock):
    author_mock = MagicMock(spec_set=True) 
    # del author_mock.name # This would cause AttributeError on access if spec_set didn't exist
    # To correctly test getattr's default, ensure 'name' is not in spec or make it raise AttributeError
    # For this test, if author_mock is a basic MagicMock without 'name', getattr will return 'N/A'.
    # If author_mock = AsyncMock(name=None) or author_mock = MagicMock(name=None), then getattr would return None.
    # The current mock_submission.author is an AsyncMock with .name attribute.
    # To test the default, we need to ensure author.name is not found by getattr.
    # One way is to make author itself None, or make author an object that doesn't have .name
    mock_submission.author = MagicMock(spec=[]) # An object with no attributes defined in spec

    content = await reddit_monitor_instance.get_post_content(mock_submission)
    
    assert content is not None 
    assert "**Author** N/A" in content 
    assert "**Title** Test Submission Title" in content 


@pytest.mark.asyncio
async def test_get_subred_no_flair(reddit_monitor_instance: RedditMonitor, mock_submission: MagicMock):
    mock_reddit = AsyncMock()
    mock_subreddit_obj = AsyncMock()
    mock_subreddit_obj.new = MagicMock(return_value=AsyncIterator([mock_submission]))
    mock_reddit.subreddit = AsyncMock(return_value=mock_subreddit_obj)
    reddit_monitor_instance.reddit = mock_reddit
    reddit_monitor_instance.get_post_content = AsyncMock(return_value="Parsed content")

    result = await reddit_monitor_instance.get_subred("testsub", None, limit=1)

    mock_reddit.subreddit.assert_called_once_with("testsub")
    mock_subreddit_obj.new.assert_called_once_with(limit=1)
    reddit_monitor_instance.get_post_content.assert_called_once_with(mock_submission)
    assert "test_submission_id" in reddit_monitor_instance.processed_posts
    assert result["test_submission_id"] == "Parsed content"


@pytest.mark.asyncio
async def test_get_subred_with_flair(reddit_monitor_instance: RedditMonitor, mock_submission: MagicMock):
    mock_reddit = AsyncMock()
    mock_subreddit_obj = AsyncMock()
    mock_subreddit_obj.search = MagicMock(return_value=AsyncIterator([mock_submission])) 
    mock_reddit.subreddit = AsyncMock(return_value=mock_subreddit_obj)
    reddit_monitor_instance.reddit = mock_reddit
    reddit_monitor_instance.get_post_content = AsyncMock(return_value="Flair content")
    flair_q = 'flair:"TestFlair"'

    result = await reddit_monitor_instance.get_subred("testsubflair", flair_q, limit=1)

    mock_reddit.subreddit.assert_called_once_with("testsubflair")
    mock_subreddit_obj.search.assert_called_once_with(query=flair_q, sort="new", limit=1, time_filter="all")
    assert result["test_submission_id"] == "Flair content"

@pytest.mark.asyncio
async def test_get_subred_api_error_retry_exceeded(reddit_monitor_instance: RedditMonitor):
    mock_reddit = AsyncMock()
    mock_original_exception = Exception("Original network problem")
    # PRAW's RequestException can be (original_exception, http_method, http_url, extra_info_dict)
    # or (original_exception, request_args_tuple, request_kwargs_dict)
    # For basic testing, providing the original exception and a message is often enough if not inspecting other attributes.
    # Let's use a simpler instantiation if the SUT only logs str(api_error)
    mock_request_exception = RequestException(mock_original_exception, ("GET", "url"), {})
    # Or, if PRAW's RequestException itself is complex to mock for all its attributes:
    # mock_request_exception = MagicMock(spec=RequestException)
    # mock_request_exception.message = "API down" # if SUT uses .message
    # mock_request_exception.__str__ = lambda self: "API down" # if SUT uses str()

    mock_reddit.subreddit = AsyncMock(side_effect=mock_request_exception)
    reddit_monitor_instance.reddit = mock_reddit
    reddit_monitor_instance.max_retries = 2 

    with patch('logging.warning') as mock_log_warning, \
         patch('logging.error') as mock_log_error, \
         patch('asyncio.sleep', AsyncMock()) as mock_sleep: 

        result = await reddit_monitor_instance.get_subred("testsub", None)

    assert mock_reddit.subreddit.call_count == 2 
    assert mock_sleep.call_count == 1 
    mock_log_error.assert_called_once()
    # The exact error message logged might depend on str(mock_request_exception)
    assert "Max retries reached for r/testsub" in mock_log_error.call_args[0][0] 
    assert result == {} 


@pytest.mark.asyncio
async def test_get_posts_single_subreddit(reddit_monitor_instance: RedditMonitor):
    reddit_monitor_instance.subreddit_names = "onesub"
    reddit_monitor_instance.flair_query = "flair:One"
    reddit_monitor_instance.get_subred = AsyncMock()
    
    await reddit_monitor_instance.get_posts()
    
    reddit_monitor_instance.get_subred.assert_called_once_with("onesub", "flair:One")

@pytest.mark.asyncio
async def test_get_posts_multiple_subreddits(reddit_monitor_instance: RedditMonitor):
    reddit_monitor_instance.subreddit_names = "subA, subB " 
    reddit_monitor_instance.flair_query = "flair:Multi"
    reddit_monitor_instance.get_subred = AsyncMock()
    
    await reddit_monitor_instance.get_posts()
    
    assert reddit_monitor_instance.get_subred.call_count == 2
    reddit_monitor_instance.get_subred.assert_any_call("subA", "flair:Multi")
    reddit_monitor_instance.get_subred.assert_any_call("subB", "flair:Multi")


@pytest.mark.asyncio
async def test_get_posts_no_subreddit_names(reddit_monitor_instance: RedditMonitor):
    reddit_monitor_instance.subreddit_names = ""
    reddit_monitor_instance.get_subred = AsyncMock()
    with patch('logging.warning') as mock_log_warning:
        await reddit_monitor_instance.get_posts()
    
    mock_log_warning.assert_called_once_with("No subreddit names configured. Skipping get_posts.")
    reddit_monitor_instance.get_subred.assert_not_called()


@pytest.mark.asyncio
async def test_close_calls_save_and_session_close(reddit_monitor_instance: RedditMonitor):
    reddit_monitor_instance.session = AsyncMock()
    reddit_monitor_instance.reddit = MagicMock() 
    reddit_monitor_instance.save_processed_posts = AsyncMock()
    
    await reddit_monitor_instance.close()
    
    reddit_monitor_instance.save_processed_posts.assert_called_once()
    reddit_monitor_instance.session.close.assert_called_once()

@pytest.mark.asyncio
async def test_close_no_session_or_reddit(reddit_monitor_instance: RedditMonitor):
    reddit_monitor_instance.session = None
    reddit_monitor_instance.reddit = None 
    reddit_monitor_instance.save_processed_posts = AsyncMock()
    
    await reddit_monitor_instance.close()
    reddit_monitor_instance.save_processed_posts.assert_not_called()
