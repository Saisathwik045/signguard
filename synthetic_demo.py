"""Read-only evidence workspace. No document ingestion or analysis backend."""
from signguard.dashboard import configure, navigation, render_page

configure("synthetic")
render_page(navigation("synthetic"), "synthetic")
