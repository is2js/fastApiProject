class RedirectException(Exception):
    def __init__(self, redirect_url: str):
        self.redirect_url = redirect_url
