"""Ephemeral synthetic documents and a self-signed test identity."""
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pymupdf
from asn1crypto import keys
from asn1crypto import x509 as asn1x509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers
from pyhanko_certvalidator.registry import SimpleCertificateStore


def unsigned():
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=300)
        page.insert_text((40, 60), "SignGuard synthetic agreement: amount 100")
        return doc.tobytes()


def signed():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SignGuard TEST ONLY")])
    now = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=1))
            .not_valid_after(now+timedelta(days=30))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    certificate = asn1x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))
    signer = signers.SimpleSigner(
        signing_cert=certificate,
        signing_key=keys.PrivateKeyInfo.load(key.private_bytes(serialization.Encoding.DER,
                                               serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption())),
        cert_registry=SimpleCertificateStore())
    output = BytesIO()
    signers.sign_pdf(IncrementalPdfFileWriter(BytesIO(unsigned())),
                     signers.PdfSignatureMetadata(field_name="TestSignature"), signer=signer, output=output)
    return output.getvalue(), certificate


def changed_revision(data, path):
    path.write_bytes(data)
    with pymupdf.open(path) as doc:
        doc[0].insert_text((40, 120), "ALTERED: amount 900")
        doc.saveIncr()
    return path.read_bytes()
