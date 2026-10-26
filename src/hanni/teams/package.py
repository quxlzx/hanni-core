"""Build a local personal Teams package and its untrusted development certificate."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from io import BytesIO
import ipaddress
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
from hanni.teams.server import validate_origin


def local_certificate(directory):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = directory / 'localhost.pem', directory / 'localhost.key'
    if cert_path.exists() and key_path.exists():
        certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
        if certificate.not_valid_after_utc > datetime.now(timezone.utc) + timedelta(days=1):
            return cert_path, key_path
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'HANNI Teams localhost development')])
    now = datetime.now(timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),
                                                   x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(key, hashes.SHA256()))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def build_package(origin, output, icon=ROOT / 'desktop' / 'hanni.ico'):
    from PIL import Image
    origin = validate_origin(origin)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        '$schema': 'https://developer.microsoft.com/json-schemas/teams/v1.19/MicrosoftTeams.schema.json',
        'manifestVersion': '1.19', 'version': '0.1.0', 'id': str(uuid5(NAMESPACE_URL, 'hanni-teams:' + origin)),
        'developer': {'name': 'HANNI', 'websiteUrl': origin + '/teams/terms',
                      'privacyUrl': origin + '/teams/privacy', 'termsOfUseUrl': origin + '/teams/terms'},
        'name': {'short': 'HANNI', 'full': 'HANNI personal assistant'},
        'description': {'short': 'Use your local HANNI assistant inside Teams.',
                        'full': 'A paired personal tab for HANNI running on this computer. Chat, read documents, review tasks and manage agent permissions using your existing local session. Requires local HANNI and the Teams launcher; does not read Teams chats.'},
        'icons': {'color': 'color.png', 'outline': 'outline.png'}, 'accentColor': '#17181B',
        'staticTabs': [{'entityId': 'hanni-personal', 'name': 'HANNI',
                        'contentUrl': origin + '/?host=teams', 'websiteUrl': origin + '/?host=teams',
                        'scopes': ['personal']}],
        'validDomains': ['localhost'], 'showLoadingIndicator': True,
    }
    with Image.open(icon) as source:
        color = source.convert('RGBA').resize((192, 192), Image.Resampling.LANCZOS)
        # Extract the existing brand mark; Teams outline icons are white with alpha.
        outline = Image.new('RGBA', (32, 32), 'white')
        mark = source.convert('L').point(lambda value: 255 if value > 145 else 0)
        outline.putalpha(mark.resize((32, 32), Image.Resampling.LANCZOS))
        def png(image):
            stream = BytesIO(); image.save(stream, format='PNG'); return stream.getvalue()
        with ZipFile(output, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest, indent=2))
            archive.writestr('color.png', png(color))
            archive.writestr('outline.png', png(outline))
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', default='https://localhost:8313')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / 'teams' / 'HANNI-Teams.zip')
    parser.add_argument('--tls-directory', type=Path, default=ROOT / 'state' / 'teams' / 'tls')
    args = parser.parse_args(argv)
    build_package(args.origin, args.output)
    cert, _ = local_certificate(args.tls_directory)
    print(f'Teams package: {args.output}\nLocal development certificate: {cert}\n'
          'The certificate has NOT been trusted. Use SETUP_TEAMS.cmd on this PC before starting Teams.')


if __name__ == '__main__':
    main()
