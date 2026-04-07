import os
import datetime
from typing import List

class Diary:
    def __init__(self, directory: str = "diary"):
        self.directory = directory
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
            
    def _get_today_file(self) -> str:
        date_str = datetime.date.today().isoformat()
        return os.path.join(self.directory, f"{date_str}.md")
        
    def log(self, role: str, content: str):
        """Append an entry to today's diary."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        filepath = self._get_today_file()
        
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"\n### [{timestamp}] {role}\n")
            f.write(f"{content}\n")
            f.write("-" * 40 + "\n")
            
    def read_diary(self, date_str: str) -> str:
        """Read a diary file by YYYY-MM-DD date."""
        filepath = os.path.join(self.directory, f"{date_str}.md")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        return f"No diary entry found for {date_str}."
        
    def list_diaries(self) -> List[str]:
        """List all available diary dates."""
        files = []
        for f in os.listdir(self.directory):
            if f.endswith(".md"):
                files.append(f.replace(".md", ""))
        return sorted(files)
