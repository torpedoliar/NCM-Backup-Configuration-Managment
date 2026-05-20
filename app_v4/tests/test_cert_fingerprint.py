from app_v4.tools.cert_fingerprint import cert_fingerprint_sha256


def test_cert_fingerprint_formats_sha256(tmp_path):
    cert = tmp_path / "cert.der"
    cert.write_bytes(b"certificate")

    fingerprint = cert_fingerprint_sha256(cert)

    assert len(fingerprint.split(":")) == 32
    assert fingerprint == fingerprint.upper()
