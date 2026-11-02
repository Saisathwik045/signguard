"""SignGuard: import heavy parsers only when analysis starts, after worker limits are installed."""


def analyze_pdf(*args, **kwargs):
    from .pipeline import analyze_pdf as implementation
    return implementation(*args, **kwargs)


__all__ = ["analyze_pdf"]
