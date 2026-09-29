import os
import warnings

# Windows Application Control on the dev machine blocks SQLAlchemy's compiled extension (pulled in by LlamaIndex);
# the pure-Python fallback is functionally identical.
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
warnings.filterwarnings("ignore", message=".*langchain-community.*")


def _stub_grpc_if_blocked() -> None:
    """Windows Application Control on the dev laptop can block grpc's compiled module. qdrant-client imports grpc at
    import time but local (on-disk) mode never uses it, so a stub keeps local mode working. No effect where grpc loads."""
    import sys
    import types

    try:
        import grpc  # noqa: F401
        return
    except ImportError:
        pass

    class _Any:
        def __init__(self, *a, **k): pass
        def __call__(self, *a, **k): return _Any()
        def __getattr__(self, n): return _Any()
        def __mro_entries__(self, bases): return (object,)

    class _Stub(types.ModuleType):
        def __getattr__(self, n): return _Any()

    for name in ("grpc", "grpc.aio", "grpc._compression", "grpc.experimental"):
        sys.modules[name] = _Stub(name)


_stub_grpc_if_blocked()
