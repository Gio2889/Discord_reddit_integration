import os
from supabase import create_client, Client

class SupabaseConnector():
    def __init__(self):
        self.url: str = os.environ.get("SUPABASE_URL")
        self.key: str = os.environ.get("SUPABASE_KEY")
        self.supabase: Client = create_client(self.url, self.key)
        self.table_title : str = "published posts"

    def insert_entry(self, table: str, entry: dict):
        """Inserts a single entry into the specified table."""
        response = self.supabase.table(table).insert(entry).execute()
        return response
    
    def insert_entries(self, table: str, entries: list):
        """Inserts multiple entries into the specified table."""
        response = self.supabase.table(table).insert(entries).execute()
        return response
    
    def check_entries():
        pass