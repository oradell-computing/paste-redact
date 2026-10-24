"""Every built-in pattern, with the look-alikes that must stay untouched.

All values are fakes: AWS's documented example keys and account IDs, RFC 5737 addresses
and example.com.
"""

import pytest
from conftest import Runner

# Key-shaped values are stored reversed and flipped at runtime, so no secret scanner sees
# a key in the source. They are the fake examples from the AWS docs.
AKID = "ELPMAXE7NNDOFSOIAIKA"[::-1]
STS_AKID = AKID.replace("AKIA", "ASIA")
EXAMPLE_VALUE = "YEKELPMAXEYCifRxPb/GNEDM7K/IMEFntUXrlaJw"[::-1]  # 40 characters
GIT_HASH = "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3"  # 40 hex characters
UUID = "123e4567-e89b-12d3-a456-42661417400a"


def private_key(kind: str, body: str) -> str:
    """A PEM block; the dashes are built at runtime so no literal block exists in the file."""
    dashes = "-" * 5
    label = f"{kind} PRIVATE KEY".lstrip()
    return f"{dashes}BEGIN {label}{dashes}\n{body}\n{dashes}END {label}{dashes}"


PRIVATE_KEY = private_key("RSA", ("fake" * 12 + "\n") * 2 + "fake==")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # state / code / code_challenge / code_verifier query parameters
        ("GET /cb?state=abc123&x=1", "GET /cb?state=REDACTED&x=1"),
        ("?code=4/0AbCdEf&state=xyz", "?code=REDACTED&state=REDACTED"),
        (
            "code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            "code_challenge=REDACTED",
        ),
        (
            "code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
            "code_verifier=REDACTED",
        ),
        # AWS access key IDs
        pytest.param(f"key {AKID} here", "key ACCESS_KEY_ID here", id="akia"),
        pytest.param(f"key {STS_AKID} here", "key ACCESS_KEY_ID here", id="asia"),
        # AWS secret access keys, in the shapes they show up in
        pytest.param(
            f"aws_secret_access_key = {EXAMPLE_VALUE}",
            "aws_secret_access_key = SECRET_KEY",
            id="secret-key-assignment",
        ),
        pytest.param(
            f'"SecretAccessKey": "{EXAMPLE_VALUE}"',
            '"SecretAccessKey": "SECRET_KEY"',
            id="secret-key-json",
        ),
        pytest.param(
            f"SECRET_ACCESS_KEY={EXAMPLE_VALUE}",
            "SECRET_ACCESS_KEY=SECRET_KEY",
            id="secret-key-env",
        ),
        # Long tokens: 100 or more token characters
        ("tok " + "abcdefghij" * 10 + " end", "tok LONG_TOKEN end"),
        ("tok " + "a/b+c=_-" * 13 + " end", "tok LONG_TOKEN end"),
        # Private keys, including the plain "PRIVATE KEY" form
        pytest.param(
            f"before\n{PRIVATE_KEY}\nafter",
            "before\nPRIVATE_KEY\nafter",
            id="private-key-rsa",
        ),
        pytest.param(
            private_key("", "ZmFrZQ=="), "PRIVATE_KEY", id="private-key-plain"
        ),
        # Exactly 12 digits: an AWS account ID
        ("account 111122223333 ok", "account ACCOUNT ok"),
        ("arn:aws:iam::123456789012:role/x", "arn:aws:iam::ACCOUNT:role/x"),
        ("(444455556666)", "(ACCOUNT)"),
        # UUIDs
        (f"id {UUID} end", "id UUID end"),
        (f"id {UUID.upper()} end", "id UUID end"),
        # Email addresses
        ("mail jane.doe+tag@example.com now", "mail EMAIL now"),
        # IPv4 addresses
        ("from 192.0.2.44 to 198.51.100.7", "from IP to IP"),
    ],
)
def test_pattern_redacts(run: Runner, text: str, expected: str) -> None:
    result = run(text)
    assert result.out == expected
    assert result.err == ""


@pytest.mark.parametrize(
    "text",
    [
        "version 2.1145.0",
        "aws-cdk@2.1145.0 and 3.14.8",
        "timestamp 1729692000123",  # 13 digits: not an account ID
    ],
)
def test_lookalikes_stay_untouched(run: Runner, text: str) -> None:
    assert run(text).out == text


@pytest.mark.parametrize(
    "text",
    [
        "listening on 127.0.0.1",
        "bind 0.0.0.0:8080",
        f"commit {GIT_HASH}",
        f"commit {GIT_HASH[:7]}",
        "tok "
        + "abcdefghij" * 9
        + "abcdefghi",  # 99 characters: one short of a long token
        "digits 12345678901",  # 11 digits
        "error_code=5 and statement=x",  # the word must start at a boundary
        "-" * 5
        + "BEGIN CERTIFICATE"
        + "-" * 5
        + "\nZmFrZQ==\n"
        + "-" * 5
        + "END CERTIFICATE"
        + "-" * 5,
        "at user@example",  # no top-level domain
        "id 123e4567-e89b-12d3-a456-42661417400",  # one character short
    ],
)
def test_negatives_stay_untouched(run: Runner, text: str) -> None:
    assert run(text).out == text


def test_patterns_apply_in_order_on_a_mixed_log(run: Runner) -> None:
    text = (
        f"role arn:aws:iam::111122223333:role/x\nuser jane@example.com from 192.0.2.1 "
        f"via 127.0.0.1\ncommit {GIT_HASH} v2.1145.0\n"
    )
    assert run(text).out == (
        "role arn:aws:iam::ACCOUNT:role/x\nuser EMAIL from IP via 127.0.0.1\n"
        f"commit {GIT_HASH} v2.1145.0\n"
    )


def test_empty_input_gives_empty_output(run: Runner) -> None:
    result = run("")
    assert (result.out, result.err, result.code) == ("", "", 0)


def test_line_endings_and_unicode_are_preserved(run: Runner) -> None:
    text = "café ✓ 111122223333\r\nnext\r\n"
    assert run(text).out == "café ✓ ACCOUNT\r\nnext\r\n"


def test_uuid_ending_in_twelve_digits_is_masked_whole(run: Runner) -> None:
    # UUID runs before ACCOUNT, so the all-digit last group isn't taken as an account ID first.
    result = run("id 123e4567-e89b-12d3-a456-111122223333 end")
    assert result.out == "id UUID end"
