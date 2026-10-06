"""
Generates human-friendly join codes for courses.

6 characters, uppercase, from an alphabet that omits easily confused
characters (0/O, 1/I/L, 2/Z, 5/S).
Entropy = 30^6 ≈ 729 million combos — plenty for enrollment codes.
"""

import secrets

ALPHABET = "ABCDEFGHJKMNPQRTUVWXY346789"
CODE_LENGTH = 6


def generate_join_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))