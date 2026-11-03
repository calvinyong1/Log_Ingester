from sqlalchemy import Integer
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import FunctionElement


class bucket_index(FunctionElement):  # noqa: N801 - reads like a SQL function
    """Index of the fixed-width time bucket a timestamp falls in.

    `bucket_index(ts, start_epoch, width_seconds)` is
    floor((epoch(ts) - start_epoch) / width_seconds), computed in the database
    so the histogram never loads rows into Python. SQLAlchemy has no portable
    epoch/floor, hence the per-dialect compilation.
    """

    type = Integer()
    inherit_cache = True


@compiles(bucket_index)
def _compile_default(element, compiler, **kw) -> str:
    ts, start, width = (compiler.process(c, **kw) for c in element.clauses)
    # Explicit casts: asyncpg infers parameter types from context and rejects
    # a Python float where it expects numeric.
    return (
        f"CAST(FLOOR((CAST(EXTRACT(EPOCH FROM {ts}) AS DOUBLE PRECISION)"
        f" - CAST({start} AS DOUBLE PRECISION))"
        f" / CAST({width} AS DOUBLE PRECISION)) AS INTEGER)"
    )


@compiles(bucket_index, "sqlite")
def _compile_sqlite(element, compiler, **kw) -> str:
    ts, start, width = (compiler.process(c, **kw) for c in element.clauses)
    # SQLite may lack FLOOR; CAST truncates toward zero, which equals floor
    # because the query only selects rows with ts >= start.
    return (
        f"CAST((CAST(strftime('%s', {ts}) AS REAL) - {start}) / {width} AS INTEGER)"
    )
