"""Where the suite writes what a person may look at afterwards.

Every screenshot the tests render shows the sample data of
tests/sample_data.py (nodes named laptop, server-dev, server-prod; dates in
May 2026), never a real daemon. The directory name says so, so a picture
found there is not mistaken for the running interface.
"""
import os
import tempfile

SCREENSHOT_DIR = tempfile.mkdtemp(prefix="opensnitch-sample-data-screenshots-")


def screenshot_path(name):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    return os.path.join(SCREENSHOT_DIR, name if name.endswith(".png") else name + ".png")
