import os
import warnings

# Windows Application Control on the dev machine blocks SQLAlchemy's compiled extension (pulled in by LlamaIndex);
# the pure-Python fallback is functionally identical.
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
warnings.filterwarnings("ignore", message=".*langchain-community.*")
