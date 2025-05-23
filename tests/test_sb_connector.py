import pytest
import sys 
import os
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.SB_connector import SupabaseConnector
from postgrest.exceptions import APIError 

# --- Fixtures ---

@pytest.fixture
def mock_env_vars_valid():
    with patch.dict(os.environ, {
        "SUPABASE_URL": "http://test.supabase.co",
        "SUPABASE_KEY": "test_supabase_key",
    }) as patched_env:
        yield patched_env

@pytest.fixture
def mock_env_vars_invalid():
    with patch.dict(os.environ, {}, clear=True) as patched_env:
        yield patched_env

@pytest.fixture
def mock_supabase_client():
    client = MagicMock()
    select_query_mock = MagicMock()
    select_query_mock.execute = MagicMock() 
    in_filter_mock = MagicMock()
    in_filter_mock.execute = MagicMock() 
    select_query_mock.in_ = MagicMock(return_value=in_filter_mock)
    insert_query_mock = MagicMock()
    insert_query_mock.execute = MagicMock() 
    table_mock = MagicMock()
    table_mock.select = MagicMock(return_value=select_query_mock)
    table_mock.insert = MagicMock(return_value=insert_query_mock)
    client.table = MagicMock(return_value=table_mock)
    return client

@pytest.fixture
def connector(mock_env_vars_valid, mock_supabase_client):
    # Patch create_client where it's looked up by SB_connector.py
    with patch('src.utils.SB_connector.create_client', return_value=mock_supabase_client) as mock_create_client:
        mock_response_data = MagicMock()
        mock_response_data.data = [{"id": "init_id1"}, {"id": "init_id2"}]
        mock_response_data.error = None # Ensure no error for successful init
        mock_supabase_client.table.return_value.select.return_value.execute.return_value = mock_response_data
        
        conn = SupabaseConnector()
        # conn.supabase is already set by __init__ if create_client was successful
        # Reset execute mock for subsequent specific tests if it was configured too generally above
        mock_supabase_client.table.return_value.select.return_value.execute.reset_mock(return_value=True, side_effect=True)
        yield conn


# --- Test Cases ---

def test_connector_init_success(mock_env_vars_valid, mock_supabase_client):
    with patch('src.utils.SB_connector.create_client', return_value=mock_supabase_client) as mock_create_client, \
         patch('src.utils.SB_connector.logging') as mock_logging:
        
        mock_response = MagicMock()
        mock_response.data = [{'id': 'id1'}, {'id': 'id2'}]
        mock_response.error = None
        mock_supabase_client.table.return_value.select.return_value.execute.return_value = mock_response

        connector_instance = SupabaseConnector()

        mock_create_client.assert_called_once_with("http://test.supabase.co", "test_supabase_key")
        assert connector_instance.supabase == mock_supabase_client
        assert connector_instance.table_title == "published posts"
        
        mock_supabase_client.table.return_value.select.assert_called_with("id")
        mock_supabase_client.table.return_value.select.return_value.execute.assert_called_once()
        assert connector_instance.database_ids == ['id1', 'id2']
        mock_logging.info.assert_any_call("Successfully connected to Supabase.")

def test_connector_init_missing_env_vars(mock_env_vars_invalid): # No need for mock_supabase_client here
    with patch('src.utils.SB_connector.create_client') as mock_create_client, \
         patch('src.utils.SB_connector.logging') as mock_logging:
        connector_instance = SupabaseConnector()
    assert connector_instance.supabase is None
    mock_logging.error.assert_called_with("Supabase URL or Key not provided in environment variables.")
    mock_create_client.assert_not_called() # create_client should not be called if env vars are missing

def test_connector_init_create_client_exception(mock_env_vars_valid):
    with patch('src.utils.SB_connector.create_client', side_effect=Exception("Connection failed")) as mock_create_client, \
         patch('src.utils.SB_connector.logging') as mock_logging:
        connector_instance = SupabaseConnector()
    assert connector_instance.supabase is None # Supabase client should not be set
    mock_create_client.assert_called_once()
    mock_logging.error.assert_called_with("Failed to create Supabase client: Connection failed", exc_info=True)
    assert not hasattr(connector_instance, 'database_ids') # database_ids should not be set if supabase client fails

def test_connector_init_get_post_ids_fails(mock_env_vars_valid, mock_supabase_client):
     with patch('src.utils.SB_connector.create_client', return_value=mock_supabase_client), \
          patch('src.utils.SB_connector.logging') as mock_logging:
        
        error_response = MagicMock()
        error_response.data = None 
        error_response.error = MagicMock() 
        error_response.error.message = "Simulated DB error during get_post_ids"
        mock_supabase_client.table.return_value.select.return_value.execute.return_value = error_response

        connector_instance = SupabaseConnector()
        assert connector_instance.database_ids == [] 
        mock_logging.warning.assert_any_call("Failed to initialize database_ids. Will start with an empty set.")


# --- insert_entry tests ---
def test_insert_entry_success(connector: SupabaseConnector, mock_supabase_client):
    entry_data = {"id": "test_id", "title": "Test Title"}
    mock_response = MagicMock()
    mock_response.data = [entry_data] 
    mock_response.error = None
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value = mock_response

    with patch('src.utils.SB_connector.logging') as mock_logging:
        response = connector.insert_entry(entry_data)

    mock_supabase_client.table.assert_called_with(connector.table_title)
    mock_supabase_client.table.return_value.insert.assert_called_with(entry_data)
    mock_supabase_client.table.return_value.insert.return_value.execute.assert_called_once()
    assert response == mock_response
    mock_logging.info.assert_called_with(f"Successfully inserted 1 entry into '{connector.table_title}'.")

def test_insert_entry_custom_table(connector: SupabaseConnector, mock_supabase_client):
    entry_data = {"id": "custom_id", "data": "value"}
    custom_table = "my_custom_table"
    mock_response = MagicMock(data=[entry_data], error=None)
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value = mock_response
    
    connector.insert_entry(entry_data, table=custom_table)
    
    mock_supabase_client.table.assert_called_with(custom_table)
    mock_supabase_client.table.return_value.insert.assert_called_with(entry_data)

def test_insert_entry_api_error(connector: SupabaseConnector, mock_supabase_client):
    entry_data = {"id": "fail_id"}
    mock_api_error = APIError({"message": "Insertion failed", "code": "123", "hint": "Check permissions", "details": "Some details"})
    mock_supabase_client.table.return_value.insert.return_value.execute.side_effect = mock_api_error

    with patch('src.utils.SB_connector.logging') as mock_logging:
        response = connector.insert_entry(entry_data)

    assert response is None
    mock_logging.error.assert_called_with(
        f"APIError inserting entry into '{connector.table_title}': {mock_api_error.message}", exc_info=True
    )

def test_insert_entry_supabase_client_none(mock_env_vars_invalid): 
    # Create instance with invalid env so supabase is None
    with patch('src.utils.SB_connector.create_client', return_value=None), \
         patch('src.utils.SB_connector.SupabaseConnector.get_post_ids', return_value=[]): # Mock get_post_ids for init
        conn = SupabaseConnector() # This will set conn.supabase to None due to missing env or create_client failure
    
    # Explicitly ensure supabase is None if the above setup isn't enough
    conn.supabase = None

    with patch('src.utils.SB_connector.logging') as mock_logging:
        response = conn.insert_entry({"id": "any"})
    assert response is None
    mock_logging.error.assert_called_with("Supabase client not initialized. Cannot insert entry.")


# --- insert_entries tests ---
def test_insert_entries_success(connector: SupabaseConnector, mock_supabase_client):
    entries_data = [{"id": "id1"}, {"id": "id2"}]
    mock_response = MagicMock(data=entries_data, error=None)
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value = mock_response

    with patch('src.utils.SB_connector.logging') as mock_logging:
        response = connector.insert_entries(entries_data)

    mock_supabase_client.table.assert_called_with(connector.table_title)
    mock_supabase_client.table.return_value.insert.assert_called_with(entries_data)
    assert response == mock_response
    mock_logging.info.assert_called_with(f"Successfully inserted {len(entries_data)} entries into '{connector.table_title}'.")

def test_insert_entries_empty_list(connector: SupabaseConnector):
    with patch('src.utils.SB_connector.logging') as mock_logging:
        response = connector.insert_entries([])
    assert response is None 
    mock_logging.info.assert_called_with("No entries provided to insert.")


# --- get_post_ids tests ---
def test_get_post_ids_success(connector: SupabaseConnector, mock_supabase_client):
    db_data = [{"id": "id10"}, {"id": "id20"}]
    mock_response = MagicMock(data=db_data, error=None)
    mock_supabase_client.table.return_value.select.return_value.execute.return_value = mock_response

    with patch('src.utils.SB_connector.logging') as mock_logging:
        ids = connector.get_post_ids()

    mock_supabase_client.table.assert_called_with(connector.table_title)
    mock_supabase_client.table.return_value.select.assert_called_with("id")
    assert ids == ["id10", "id20"]
    mock_logging.info.assert_called_with(f"Successfully fetched 2 IDs from '{connector.table_title}'.")

def test_get_post_ids_empty_response(connector: SupabaseConnector, mock_supabase_client):
    mock_response = MagicMock(data=[], error=None) 
    mock_supabase_client.table.return_value.select.return_value.execute.return_value = mock_response
    ids = connector.get_post_ids()
    assert ids == []

def test_get_post_ids_api_error(connector: SupabaseConnector, mock_supabase_client):
    mock_api_error = APIError({"message": "Selection failed", "code": "123", "hint": None, "details": None})
    mock_supabase_client.table.return_value.select.return_value.execute.side_effect = mock_api_error
    with patch('src.utils.SB_connector.logging') as mock_logging:
        ids = connector.get_post_ids()
    assert ids is None
    mock_logging.error.assert_called_with(
        f"APIError fetching post IDs from '{connector.table_title}': {mock_api_error.message}", exc_info=True
    )


# --- check_entries tests ---
def test_check_entries_found_some(connector: SupabaseConnector, mock_supabase_client):
    id_list_to_check = ["id1", "id2", "id3"]
    db_response_data = [{"id": "id1"}, {"id": "id3"}] 
    mock_response = MagicMock(data=db_response_data, error=None)
    execute_mock = mock_supabase_client.table.return_value.select.return_value.in_.return_value.execute
    execute_mock.return_value = mock_response

    with patch('src.utils.SB_connector.logging') as mock_logging:
        existing_ids = connector.check_entries(id_list_to_check)

    mock_supabase_client.table.return_value.select.assert_called_with("id")
    mock_supabase_client.table.return_value.select.return_value.in_.assert_called_with("id", id_list_to_check)
    assert existing_ids == ["id1", "id3"]
    mock_logging.info.assert_called_with(f"Checked {len(id_list_to_check)} IDs against '{connector.table_title}'. Found {len(existing_ids)} existing IDs.")

def test_check_entries_none_found(connector: SupabaseConnector, mock_supabase_client):
    id_list_to_check = ["id_unknown1", "id_unknown2"]
    mock_response = MagicMock(data=[], error=None)
    execute_mock = mock_supabase_client.table.return_value.select.return_value.in_.return_value.execute
    execute_mock.return_value = mock_response
    
    existing_ids = connector.check_entries(id_list_to_check)
    assert existing_ids == []

def test_check_entries_empty_input_list(connector: SupabaseConnector):
    with patch('src.utils.SB_connector.logging') as mock_logging:
        existing_ids = connector.check_entries([])
    assert existing_ids == []
    mock_logging.debug.assert_called_with("Empty ID list provided to check_entries. Returning empty list.")

def test_check_entries_api_error(connector: SupabaseConnector, mock_supabase_client):
    id_list_to_check = ["id1", "id2"]
    execute_mock = mock_supabase_client.table.return_value.select.return_value.in_.return_value.execute
    mock_api_error = APIError({"message": "Filter failed", "code": "123", "hint": None, "details": None})
    execute_mock.side_effect = mock_api_error
    
    with patch('src.utils.SB_connector.logging') as mock_logging:
        existing_ids = connector.check_entries(id_list_to_check)
    
    assert existing_ids is None
    mock_logging.error.assert_called_with(
        f"APIError checking entries in '{connector.table_title}': {mock_api_error.message}", exc_info=True
    )
