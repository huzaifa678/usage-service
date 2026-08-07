import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture(autouse=True)
def _disable_observability():
    with patch("usage_common.pipeline.setup_observability", lambda *a, **k: None):
        yield
