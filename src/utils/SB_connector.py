import os
import logging
from supabase import create_client, Client
from postgrest.exceptions import APIError # For handling Supabase specific API errors

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

class SupabaseConnector:
    def __init__(self):
        self.url: str = os.environ.get("SUPABASE_URL")
        self.key: str = os.environ.get("SUPABASE_KEY")
        self.supabase: Client = None
        self.table_title: str = "published posts" # Default table name
        
        if not self.url or not self.key:
            logging.error("Supabase URL or Key not provided in environment variables.")
            # Depending on application design, might raise an exception or set a state indicating no DB connection
            return

        try:
            self.supabase = create_client(self.url, self.key)
            logging.info("Successfully connected to Supabase.")
        except Exception as e:
            logging.error(f"Failed to create Supabase client: {e}", exc_info=True)
            # Again, application might need to handle this state
            return

        self.database_ids = self.get_post_ids() # Initialize with current IDs from DB
        if self.database_ids is None: # get_post_ids will return None on failure
             logging.warning("Failed to initialize database_ids. Will start with an empty set.")
             self.database_ids = []


    def insert_entry(self, entry: dict, table: str = None):
        """Inserts a single entry into the specified table.
        Returns the API response or None on failure."""
        if not self.supabase:
            logging.error("Supabase client not initialized. Cannot insert entry.")
            return None
        if table is None:
            table = self.table_title
        
        try:
            response = self.supabase.table(table).insert(entry).execute()
            if hasattr(response, 'data') and response.data:
                logging.info(f"Successfully inserted 1 entry into '{table}'.")
            elif hasattr(response, 'error') and response.error:
                 logging.error(f"Error inserting entry into '{table}': {response.error.message}")
                 return None
            return response
        except APIError as e:
            logging.error(f"APIError inserting entry into '{table}': {e.message}", exc_info=True)
            return None
        except Exception as e: # Catch other potential errors (network, etc.)
            logging.error(f"Unexpected error inserting entry into '{table}': {e}", exc_info=True)
            return None

    def insert_entries(self, entries: list, table: str = None):
        """Inserts multiple entries into the specified table.
        Returns the API response or None on failure."""
        if not self.supabase:
            logging.error("Supabase client not initialized. Cannot insert entries.")
            return None
        if not entries:
            logging.info("No entries provided to insert.")
            return None
        if table is None:
            table = self.table_title
        
        try:
            response = self.supabase.table(table).insert(entries).execute()
            if hasattr(response, 'data') and response.data:
                logging.info(f"Successfully inserted {len(response.data)} entries into '{table}'.")
            elif hasattr(response, 'error') and response.error:
                 logging.error(f"Error inserting entries into '{table}': {response.error.message}")
                 return None
            return response
        except APIError as e:
            logging.error(f"APIError inserting entries into '{table}': {e.message}", exc_info=True)
            return None
        except Exception as e:
            logging.error(f"Unexpected error inserting entries into '{table}': {e}", exc_info=True)
            return None

    def get_post_ids(self, table: str = None) -> list | None:
        """Fetches all post IDs from the specified table.
        Returns a list of IDs or None on failure."""
        if not self.supabase:
            logging.error("Supabase client not initialized. Cannot get post IDs.")
            return None
        if table is None:
            table = self.table_title
        
        try:
            response = self.supabase.table(table).select("id").execute()
            if hasattr(response, 'data'):
                id_list = [entry["id"] for entry in response.data if "id" in entry]
                logging.info(f"Successfully fetched {len(id_list)} IDs from '{table}'.")
                return id_list
            elif hasattr(response, 'error') and response.error:
                logging.error(f"Error fetching post IDs from '{table}': {response.error.message}")
                return None # Indicate failure
            return [] # No data and no error means empty table or no matching entries
        except APIError as e:
            logging.error(f"APIError fetching post IDs from '{table}': {e.message}", exc_info=True)
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching post IDs from '{table}': {e}", exc_info=True)
            return None

    def check_entries(self, id_list: list, table: str = None) -> list | None:
        """Checks which IDs from the given list already exist in the specified table.
        Returns a list of existing IDs or None on failure."""
        if not self.supabase:
            logging.error("Supabase client not initialized. Cannot check entries.")
            return None
        if not id_list:
            logging.debug("Empty ID list provided to check_entries. Returning empty list.")
            return []
        if table is None:
            table = self.table_title
        
        try:
            # Use the 'in' filter to check for multiple IDs
            response = self.supabase.table(table).select("id").in_("id", id_list).execute()
            
            if hasattr(response, 'data'):
                existing_ids = [entry["id"] for entry in response.data if "id" in entry]
                logging.info(f"Checked {len(id_list)} IDs against '{table}'. Found {len(existing_ids)} existing IDs.")
                return existing_ids
            elif hasattr(response, 'error') and response.error:
                logging.error(f"Error checking entries in '{table}': {response.error.message}")
                return None # Indicate failure
            return [] # No data and no error
        except APIError as e:
            logging.error(f"APIError checking entries in '{table}': {e.message}", exc_info=True)
            return None
        except Exception as e:
            logging.error(f"Unexpected error checking entries in '{table}': {e}", exc_info=True)
            return None
