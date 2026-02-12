"""
Upload Session Manager.
Handles multi-packet file uploads.
"""

class UploadSession:
    """
    Tracks state of file uploads.
    """
    def __init__(self, session_id: str, file_path: str, total_size: int):
        self.session_id = session_id
        self.file_path = file_path
        self.total_size = total_size
        # TODO: Track chunks
