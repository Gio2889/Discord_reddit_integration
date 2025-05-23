import pytest
import asyncio
import sys 
import os 
from unittest.mock import AsyncMock, MagicMock, patch, ANY 
from io import BytesIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.mosaic_maker import fetch_image, imager_puller, mosaic_maker
import aiohttp
from PIL import Image, UnidentifiedImageError
import matplotlib.pyplot as plt 


# --- Fixtures ---

@pytest.fixture
def mock_aiohttp_session():
    session_mock = MagicMock(spec=aiohttp.ClientSession)
    response_mock = AsyncMock(spec=aiohttp.ClientResponse)
    response_mock.status = 200
    response_mock.headers = {'Content-Type': 'image/png'}
    response_mock.read = AsyncMock(return_value=b"fake_image_bytes")
    async_context_manager_mock = AsyncMock()
    async_context_manager_mock.__aenter__.return_value = response_mock
    session_mock.get = MagicMock(return_value=async_context_manager_mock)
    return session_mock

@pytest.fixture
def mock_pil_image():
    img_mock = MagicMock(spec=Image.Image)
    img_mock.copy = MagicMock(return_value=img_mock) 
    img_mock.thumbnail = MagicMock()
    return img_mock

# --- Tests for fetch_image ---

@pytest.mark.asyncio
async def test_fetch_image_success(mock_aiohttp_session, mock_pil_image):
    url = "http://example.com/image.png"
    with patch('PIL.Image.open', return_value=mock_pil_image) as mock_image_open:
        result_image = await fetch_image(mock_aiohttp_session, url)
    mock_aiohttp_session.get.assert_called_once_with(url)
    mock_aiohttp_session.get.return_value.__aenter__.return_value.read.assert_called_once()
    assert mock_image_open.call_count == 1
    args, _ = mock_image_open.call_args
    assert isinstance(args[0], BytesIO)
    assert args[0].getvalue() == b"fake_image_bytes"
    assert result_image == mock_pil_image

@pytest.mark.asyncio
async def test_fetch_image_http_error(mock_aiohttp_session):
    url = "http://example.com/notfound.png"
    mock_aiohttp_session.get.return_value.__aenter__.return_value.status = 404 
    with patch('src.utils.mosaic_maker.logging') as mock_logging:
        result_image = await fetch_image(mock_aiohttp_session, url)
    assert result_image is None
    mock_logging.warning.assert_called_once_with(f"Failed to fetch {url}. Status: 404")

@pytest.mark.asyncio
async def test_fetch_image_network_error(mock_aiohttp_session):
    url = "http://example.com/network_error.png"
    mock_aiohttp_session.get.side_effect = aiohttp.ClientError("Network connection failed")
    with patch('src.utils.mosaic_maker.logging') as mock_logging:
        result_image = await fetch_image(mock_aiohttp_session, url)
    assert result_image is None
    mock_logging.error.assert_called_once_with(
        f"Network error fetching {url}: Network connection failed", exc_info=True
    )

@pytest.mark.asyncio
async def test_fetch_image_unidentified_image_error(mock_aiohttp_session):
    url = "http://example.com/bad_image.png"
    with patch('PIL.Image.open', side_effect=UnidentifiedImageError("Cannot identify image")) as mock_image_open, \
         patch('src.utils.mosaic_maker.logging') as mock_logging:
        result_image = await fetch_image(mock_aiohttp_session, url)
    assert result_image is None
    mock_image_open.assert_called_once()
    mock_logging.warning.assert_called_once_with(
        f"Cannot identify image from URL: {url}. Content type: image/png"
    )

@pytest.mark.asyncio
async def test_fetch_image_pil_processing_error(mock_aiohttp_session):
    url = "http://example.com/pil_error.png"
    with patch('PIL.Image.open', side_effect=Exception("PIL broke")) as mock_image_open, \
         patch('src.utils.mosaic_maker.logging') as mock_logging:
        result_image = await fetch_image(mock_aiohttp_session, url)
    assert result_image is None
    mock_image_open.assert_called_once()
    mock_logging.error.assert_called_once_with(
        f"Error processing image data from {url}: PIL broke", exc_info=True
    )

# --- Tests for imager_puller ---

@pytest.mark.asyncio
async def test_imager_puller_success_multiple_images(mock_pil_image):
    urls = ["url1", "url2"]
    with patch('src.utils.mosaic_maker.fetch_image', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_pil_image 
        images = await imager_puller(urls)
    assert mock_fetch.call_count == len(urls)
    mock_fetch.assert_any_call(ANY, "url1") 
    mock_fetch.assert_any_call(ANY, "url2")
    assert len(images) == len(urls)
    assert all(img == mock_pil_image for img in images)

@pytest.mark.asyncio
async def test_imager_puller_some_fail(mock_pil_image):
    urls = ["ok_url", "bad_url", "good_url"]
    async def fetch_side_effect(session, url):
        if url == "bad_url": return None
        return mock_pil_image 
    with patch('src.utils.mosaic_maker.fetch_image', side_effect=fetch_side_effect):
        images = await imager_puller(urls)
    assert len(images) == 2 
    assert all(img == mock_pil_image for img in images)

@pytest.mark.asyncio
async def test_imager_puller_all_fail():
    urls = ["bad1", "bad2"]
    with patch('src.utils.mosaic_maker.fetch_image', AsyncMock(return_value=None)), \
         patch('src.utils.mosaic_maker.logging') as mock_logging:
        images = await imager_puller(urls)
    assert len(images) == 0
    mock_logging.warning.assert_called_once_with("No images successfully fetched or processed from the provided list.")

@pytest.mark.asyncio
async def test_imager_puller_empty_list():
    with patch('src.utils.mosaic_maker.logging') as mock_logging:
        images = await imager_puller([])
    assert len(images) == 0
    mock_logging.info.assert_called_once_with("Empty image_list provided to imager_puller.")

# --- Tests for mosaic_maker ---

@patch('matplotlib.pyplot.subplots', return_value=(MagicMock(spec=plt.Figure), MagicMock(spec=plt.Axes)))
@patch('matplotlib.pyplot.figure', return_value=MagicMock(spec=plt.Figure))
@patch('matplotlib.pyplot.tight_layout')
@patch('matplotlib.pyplot.savefig')
@patch('matplotlib.pyplot.close')
@pytest.mark.asyncio
async def test_mosaic_maker_single_image(mock_plt_close, mock_plt_savefig, mock_plt_tight_layout, mock_plt_figure, mock_plt_subplots, mock_pil_image):
    with patch('src.utils.mosaic_maker.imager_puller', AsyncMock(return_value=[mock_pil_image])):
        buffer = await mosaic_maker(["url1"])
    mock_pil_image.copy.assert_called_once()
    mock_pil_image.thumbnail.assert_called_once_with((1024, 1024), Image.Resampling.LANCZOS)
    mock_plt_subplots.assert_called_once_with(1, 1, figsize=(5,5))
    fig_mock, ax_mock = mock_plt_subplots.return_value
    ax_mock.imshow.assert_called_once_with(mock_pil_image) 
    ax_mock.axis.assert_called_once_with("off")
    fig_mock.tight_layout.assert_called_once()
    fig_mock.savefig.assert_called_once() # Check it's called, specific args later if needed
    assert isinstance(buffer, BytesIO)
    mock_plt_close.assert_called_once_with(fig_mock)


@patch('matplotlib.pyplot.subplots', return_value=(MagicMock(spec=plt.Figure), [MagicMock(spec=plt.Axes), MagicMock(spec=plt.Axes)])) 
@patch('matplotlib.pyplot.figure') 
@patch('matplotlib.pyplot.tight_layout')
@patch('matplotlib.pyplot.savefig')
@patch('matplotlib.pyplot.close')
@pytest.mark.asyncio
async def test_mosaic_maker_two_images(mock_plt_close, mock_plt_savefig, mock_plt_tight_layout, mock_plt_figure, mock_plt_subplots, mock_pil_image):
    image1_mock = MagicMock(spec=Image.Image); image1_mock.copy.return_value = image1_mock; image1_mock.thumbnail = MagicMock()
    image2_mock = MagicMock(spec=Image.Image); image2_mock.copy.return_value = image2_mock; image2_mock.thumbnail = MagicMock()
    images = [image1_mock, image2_mock]
    with patch('src.utils.mosaic_maker.imager_puller', AsyncMock(return_value=images)):
        await mosaic_maker(["url1", "url2"])
    mock_plt_subplots.assert_called_once_with(1, 2, figsize=(10,5))
    fig_mock, axes_mocks = mock_plt_subplots.return_value
    axes_mocks[0].imshow.assert_called_once_with(image1_mock)
    axes_mocks[1].imshow.assert_called_once_with(image2_mock)
    mock_plt_close.assert_called_once_with(fig_mock)

@patch('matplotlib.pyplot.subplots')
@patch('matplotlib.pyplot.figure') 
@patch('matplotlib.pyplot.tight_layout')
@patch('matplotlib.pyplot.savefig')
@patch('matplotlib.pyplot.close')
@pytest.mark.asyncio
async def test_mosaic_maker_three_images(mock_plt_close, mock_plt_savefig, mock_plt_tight_layout, mock_plt_figure, mock_plt_subplots, mock_pil_image):
    images = [mock_pil_image] * 3
    fig_mock = MagicMock(spec=plt.Figure)
    mock_plt_figure.return_value = fig_mock
    gs_mock = MagicMock()
    fig_mock.add_gridspec = MagicMock(return_value=gs_mock)
    ax_mocks = [MagicMock(spec=plt.Axes) for _ in range(3)]
    fig_mock.add_subplot = MagicMock(side_effect=ax_mocks)
    with patch('src.utils.mosaic_maker.imager_puller', AsyncMock(return_value=images)):
        await mosaic_maker(["u1", "u2", "u3"])
    mock_plt_figure.assert_called_once_with(figsize=(10,10))
    fig_mock.add_gridspec.assert_called_once_with(2,2)
    assert fig_mock.add_subplot.call_count == 3
    for ax_mock in ax_mocks:
        ax_mock.imshow.assert_called_once()
    mock_plt_close.assert_called_once_with(fig_mock)

@patch('matplotlib.pyplot.subplots') 
@patch('matplotlib.pyplot.figure') 
@patch('matplotlib.pyplot.tight_layout')
@patch('matplotlib.pyplot.savefig')
@patch('matplotlib.pyplot.close')
@pytest.mark.asyncio
async def test_mosaic_maker_four_images(mock_plt_close, mock_plt_savefig, mock_plt_tight_layout, mock_plt_figure, mock_plt_subplots, mock_pil_image):
    images = [mock_pil_image] * 4
    fig_mock = MagicMock(spec=plt.Figure)
    axes_array_mocks = [MagicMock(spec=plt.Axes) for _ in range(4)]
    mock_axes_array_object = MagicMock()
    mock_axes_array_object.flatten = MagicMock(return_value=axes_array_mocks)
    mock_plt_subplots.return_value = (fig_mock, mock_axes_array_object)
    with patch('src.utils.mosaic_maker.imager_puller', AsyncMock(return_value=images)):
        await mosaic_maker(["u1","u2","u3","u4"])
    mock_plt_subplots.assert_called_once_with(2,2, figsize=(10,10))
    mock_axes_array_object.flatten.assert_called_once()
    for ax_mock in axes_array_mocks:
        ax_mock.imshow.assert_called_once()
    mock_plt_close.assert_called_once_with(fig_mock)

@patch('matplotlib.pyplot.savefig') 
@pytest.mark.asyncio
async def test_mosaic_maker_no_images_pulled(mock_plt_savefig): 
    with patch('src.utils.mosaic_maker.imager_puller', AsyncMock(return_value=[])) as mock_puller, \
         patch('src.utils.mosaic_maker.logging') as mock_logging:
        result = await mosaic_maker(["some_url"]) 
    assert result is None
    mock_puller.assert_called_once_with(["some_url"])
    mock_logging.warning.assert_called_with("imager_puller returned no images for mosaic_maker.")
    mock_plt_savefig.assert_not_called()

@pytest.mark.asyncio
async def test_mosaic_maker_empty_input_list():
     with patch('src.utils.mosaic_maker.logging') as mock_logging:
        result = await mosaic_maker([])
     assert result is None
     mock_logging.warning.assert_called_with("mosaic_maker received an empty image_list.")

@pytest.mark.asyncio
async def test_mosaic_maker_matplotlib_error(mocker, mock_pil_image):
    # Mock matplotlib functions using mocker
    mock_fig_instance = MagicMock(spec=plt.Figure)
    mock_ax_instance = MagicMock(spec=plt.Axes)

    mocker.patch('matplotlib.pyplot.subplots', return_value=(mock_fig_instance, mock_ax_instance))
    mocker.patch('matplotlib.pyplot.figure', return_value=mock_fig_instance) # Ensure figure also returns the same mock if called
    mocker.patch('matplotlib.pyplot.tight_layout')
    # Crucially, make the savefig method *on the figure instance* raise the error
    mock_fig_instance.savefig = MagicMock(side_effect=Exception("Matplotlib save error"))
    mock_plt_close = mocker.patch('matplotlib.pyplot.close')
    
    with patch('src.utils.mosaic_maker.imager_puller', AsyncMock(return_value=[mock_pil_image])), \
         patch('src.utils.mosaic_maker.logging') as mock_logging:
        result = await mosaic_maker(["url1"])
    
    assert result is None 
    mock_logging.error.assert_called_with("Error creating mosaic with matplotlib: Matplotlib save error", exc_info=True)
    # The actual figure object (mock_fig_instance) should be passed to plt.close
    mock_plt_close.assert_called_once_with(mock_fig_instance)


@patch('matplotlib.pyplot.subplots', return_value=(MagicMock(spec=plt.Figure), MagicMock(spec=plt.Axes)))
@patch('matplotlib.pyplot.figure')
@patch('matplotlib.pyplot.tight_layout')
@patch('matplotlib.pyplot.savefig')
@patch('matplotlib.pyplot.close')
@pytest.mark.asyncio
async def test_mosaic_maker_image_resize_error(mock_plt_close, mock_plt_savefig, mock_plt_tight_layout, mock_plt_figure, mock_plt_subplots, mock_pil_image):
    good_image = MagicMock(spec=Image.Image)
    good_image_copy_mock = MagicMock(spec=Image.Image)
    good_image_copy_mock.thumbnail = MagicMock(side_effect=Exception("Thumbnail failed"))
    good_image.copy = MagicMock(return_value=good_image_copy_mock)

    with patch('src.utils.mosaic_maker.imager_puller', AsyncMock(return_value=[good_image])), \
         patch('src.utils.mosaic_maker.logging') as mock_logging:
        result = await mosaic_maker(["url1"])

    assert result is None 
    good_image.copy.assert_called_once() 
    good_image_copy_mock.thumbnail.assert_called_once() 
    mock_logging.error.assert_any_call("Error resizing image: Thumbnail failed", exc_info=True)
    mock_logging.warning.assert_called_with("No images were successfully resized.")
    mock_plt_savefig.assert_not_called() 
    assert mock_plt_close.call_count == 0
