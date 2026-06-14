"""
ids_to_uuid.py

Deterministic UUID utilities for healthcare identifiers.

We support three use-cases:

1) NPI → UUIDv5 (public, reproducible)
   --------------------------------------------------
   NPIs are already public. We produce a stable RFC-4122 UUIDv5
   using Python's built-in uuid.uuid5() with the FHIR NPI URI namespace.
   This is not for secrecy — only for systems that require UUID-typed IDs.

2) EIN/TIN → HMAC-based UUID (secret, deterministic)
   --------------------------------------------------
   TINs/EINs are from a tiny numeric domain. True uuid5 (SHA-1 + public namespace)
   is reversible by brute force. Instead we compute HMAC-SHA256(context || tin)
   using a secret key ("pepper") and then shape the first 16 bytes into a
   valid RFC-4122 UUID. We set the version nibble to 5 deliberately — to signal
   that this is a deterministic, name-style UUID — even though it is NOT the
   true uuid5 algorithm. The security comes from HMAC, not from the UUID version bit.

3) Random UUIDv4 (completely random)
   --------------------------------------------------
   For cases where you need a completely random UUID with no deterministic mapping.
   This is simply a wrapper around the standard uuid.uuid4() function.

USAGE
=====

    from ids_to_uuid import npi_to_uuid5, ein_to_uuid_hmac, tin_to_uuid_hmac, get_random_uuid4
    import uuid

    # 1) NPI → UUIDv5 (no secret)
    u1 = npi_to_uuid5("1234567890")
    print(u1)

    # 2) EIN/TIN → HMAC-based UUID (secret key required)
    pepper = bytes.fromhex("0e6f9a3f3a7b0c6fa1b8b2b2a4d5e6f70b2e1c9ad5f8a7c3e6d1c2b4a9f0e1d2")

    u2 = ein_to_uuid_hmac("12-3456789", pepper)
    print(u2)

    # scoping with "context" allows the same tin to map to different UUIDs if desired
    u3 = tin_to_uuid_hmac("987654321", pepper, context="CLAIMS")
    print(u3)

    # 3) Random UUIDv4 (no input required)
    u4 = get_random_uuid4()
    print(u4)

"""

import hmac, hashlib, uuid
from typing import Union

# ------------------------------------------------------------------------------

def _digits_only_n(s: str, n: int) -> str:
    d = "".join(ch for ch in s if ch.isdigit())
    if len(d) != n:
        raise ValueError(f"Identifier must normalize to exactly {n} digits.")
    return d

# ------------------------------------------------------------------------------

def npi_to_uuid5(
    npi: str,
    *,
    namespace: uuid.UUID = uuid.NAMESPACE_URL,
    prefix: str = "http://hl7.org/fhir/sid/us-npi/",
) -> uuid.UUID:
    """Convert a 10-digit NPI to a deterministic UUIDv5 using uuid.uuid5(). Public, not secret."""
    npi10 = _digits_only_n(npi, 10)
    name = f"{prefix}{npi10}"
    return uuid.uuid5(namespace, name)

# ------------------------------------------------------------------------------

def tin_to_uuid_hmac(
    tin: str,
    pepper_key: Union[bytes, bytearray],
    *,
    context: str = "TIN",
) -> uuid.UUID:
    """
    Deterministically map a 9-digit TIN/EIN to a UUID using HMAC-SHA256.
    This is NOT uuid5; we only set the UUID version nibble to 5 for semantic signaling.
    """
    if not isinstance(pepper_key, (bytes, bytearray)) or len(pepper_key) < 16:
        raise ValueError("pepper_key must be bytes and at least 16 bytes long.")

    tin9 = _digits_only_n(tin, 9)
    msg = (context.strip().upper() + ":" + tin9).encode("utf-8")
    dig = hmac.new(bytes(pepper_key), msg, hashlib.sha256).digest()

    raw = bytearray(dig[:16])
    raw[6] = (raw[6] & 0x0F) | (5 << 4)  # set version nibble 5 intentionally
    raw[8] = (raw[8] & 0x3F) | 0x80      # RFC 4122 variant
    return uuid.UUID(bytes=bytes(raw))

def ein_to_uuid_hmac(ein: str, pepper_key: Union[bytes, bytearray]) -> uuid.UUID:
    """Convenience wrapper explicitly marking context 'EIN'."""
    return tin_to_uuid_hmac(ein, pepper_key, context="EIN")

# ------------------------------------------------------------------------------

def get_random_uuid4() -> uuid.UUID:
    """
    Generate a random UUID version 4.
    
    This is simply a wrapper around uuid.uuid4() for consistency with the other
    UUID generation functions in this module. UUIDv4 uses random or pseudo-random
    numbers and provides no deterministic mapping from input data.
    
    Returns:
        uuid.UUID: A random UUIDv4
    """
    return uuid.uuid4()
