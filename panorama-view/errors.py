class PanoramaError(Exception):
    """Expected, human-readable processing failure."""


class IncompletePanoramaError(PanoramaError):
    def __init__(self, message):
        super().__init__(f"Incomplete panorama: {message}")
