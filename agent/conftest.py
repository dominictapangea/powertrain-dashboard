import sys
from pathlib import Path

# Make `import sql_guard` work when pytest runs from the project root.
sys.path.insert(0, str(Path(__file__).parent))
