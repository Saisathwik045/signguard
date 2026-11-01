"""Generate demonstration PDFs; no private key is saved."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.fixtures import changed_revision, signed, unsigned

output = Path("samples")
output.mkdir(exist_ok=True)
(output / "unsigned.pdf").write_bytes(unsigned())
data, _ = signed()
(output / "signed.pdf").write_bytes(data)
changed_revision(data, output / "shadow-update.pdf")
(output / "tampered.pdf").write_bytes(data.replace(b"%PDF-1.7", b"%PDF-1.6", 1))
print(f"Generated four synthetic PDFs in {output.resolve()}")
