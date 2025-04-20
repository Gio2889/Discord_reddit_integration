import os
from supabase import create_client, Client

class SupabaseConnector():
    def __init__(self):
        self.url: str = os.environ.get("SUPABASE_URL")
        self.key: str = os.environ.get("SUPABASE_KEY")
        self.supabase: Client = create_client(self.url, self.key)
        self.table_title : str = "published posts"
        self.database_ids = self.get_post_ids()

    def insert_entry(self, entry: dict,table: str = None):
        """Inserts a single entry into the specified table."""
        if table is None:
            table = self.table_title
        response = self.supabase.table(table).insert(entry).execute()
        return response
    
    def insert_entries(self, entries: list,table: str = None):
        """Inserts multiple entries into the specified table."""
        if table is None:
            table = self.table_title
        response = self.supabase.table(table).insert(entries).execute()
        return response
    
    def get_post_ids(self, table: str = None):
        """Fetches all post IDs from the specified table."""
        if table is None:
            table = self.table_title
        response = self.supabase.table(table).select('id').execute()
        if response.data:
            id_list = [entry['id'] for entry in response.data]
            return id_list
        else:
            return []

    def check_entries():
        pass