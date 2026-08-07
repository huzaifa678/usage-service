from etl.aggregate import AggregateFilter
from etl.embed import EmbedFilter
from etl.ingest import IngestFilter
from usage_common.pipeline import FilterResult, Pipeline


def build_pipeline() -> Pipeline:
    return Pipeline(IngestFilter(), AggregateFilter(), EmbedFilter())


def run() -> list[FilterResult]:
    return build_pipeline().run()
