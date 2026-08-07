from usage_common.pipeline import Filter, FilterResult, Pipeline


class _RecordingFilter(Filter):
    name = "recording"
    span_name = "usage.test.recording"

    def __init__(self, processed: int):
        self._processed = processed
        self.calls = 0

    def process(self) -> FilterResult:
        self.calls += 1
        return FilterResult(
            name=self.name,
            processed=self._processed,
            metrics={"extra": self._processed * 2},
        )


def test_filter_run_invokes_process_once_and_returns_result():
    stage = _RecordingFilter(processed=3)

    result = stage.run()

    assert stage.calls == 1
    assert result.name == "recording"
    assert result.processed == 3
    assert result.metrics == {"extra": 6}


def test_pipeline_runs_filters_in_order():
    first = _RecordingFilter(processed=1)
    second = _RecordingFilter(processed=2)

    results = Pipeline(first, second).run()

    assert [r.processed for r in results] == [1, 2]
    assert first.calls == 1
    assert second.calls == 1
