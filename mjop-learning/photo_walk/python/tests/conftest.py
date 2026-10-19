import sys
from pathlib import Path

PY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PY))
sys.path.insert(0, str(PY.parents[1] / "scripts"))   # bruto_quantity_core (alleen voor pariteitstest)
