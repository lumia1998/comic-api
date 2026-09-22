class ComicApiError(RuntimeError):
    def __init__(self, message, status_code=502, code="upstream_error", source=None):
        super().__init__(message)
        self.status_code, self.code, self.source = status_code, code, source

    def payload(self):
        return {"code": self.code, "message": str(self), "source": self.source}


class DownloadCancelled(Exception):
    pass
