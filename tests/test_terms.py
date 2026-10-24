"""The terms file, input decoding and the command-line interface."""

from pathlib import Path

from conftest import SCRIPT, Runner


def test_term_without_label_becomes_redacted(run: Runner) -> None:
    assert run("the code name is Bluebird.", terms="Bluebird\n").out == (
        "the code name is REDACTED."
    )


def test_term_with_label(run: Runner) -> None:
    assert (
        run("ping db-prod-7 now", terms="db-prod-7 => DB_HOST\n").out
        == "ping DB_HOST now"
    )


def test_empty_label_falls_back_to_redacted(run: Runner) -> None:
    assert run("a secret b", terms="secret => \n").out == "a REDACTED b"


def test_only_the_first_separator_splits_the_label(run: Runner) -> None:
    assert run("x token y", terms="token => A => B\n").out == "x A => B y"


def test_a_line_with_equals_signs_is_one_plain_term(run: Runner) -> None:
    result = run(
        "DB_PASSWORD=hunter2 and hunter2 and DB_PASSWORD", terms="DB_PASSWORD=hunter2\n"
    )
    assert result.out == "REDACTED and hunter2 and DB_PASSWORD"


def test_a_secret_pasted_as_an_assignment_never_reaches_the_output(run: Runner) -> None:
    result = run("export DB_PASSWORD=hunter2\n", terms="DB_PASSWORD=hunter2\n")
    assert result.out == "export REDACTED\n"
    assert "hunter2" not in result.out


def test_equals_signs_without_spaces_are_not_a_separator(run: Runner) -> None:
    assert run("a b=c d", terms="b=c => LABEL\n").out == "a LABEL d"
    assert run("a x=>y d", terms="x=>y\n").out == "a REDACTED d"
    assert run("a x==y d", terms="x==y\n").out == "a REDACTED d"


def test_whitespace_around_secret_and_label_is_stripped(run: Runner) -> None:
    result = run("a Bluebird b", terms="  Bluebird   =>   CLIENT  \n")
    assert result.out == "a CLIENT b"


def test_plain_term_is_stripped_too(run: Runner) -> None:
    assert run("a Bluebird b", terms="   Bluebird  \n").out == "a REDACTED b"


def test_a_line_with_an_empty_secret_is_ignored_with_a_warning(run: Runner) -> None:
    result = run("a b", terms=" => LABEL\n")
    assert result.out == "a b"
    assert "empty secret" in result.err
    assert "LABEL" not in result.err


def test_matching_is_case_insensitive_and_keeps_the_label_as_written(
    run: Runner,
) -> None:
    result = run("Acme ACME acme aCmE", terms="acme => Customer\n")
    assert result.out == "Customer Customer Customer Customer"


def test_terms_are_literal_not_regular_expressions(run: Runner) -> None:
    assert run("a.c abc a+c", terms="a.c => X\n").out == "X abc a+c"


def test_longest_term_wins_even_when_listed_last(run: Runner) -> None:
    terms = "acme => SHORT\nacme-internal => LONG\n"
    assert run("host acme-internal and acme", terms=terms).out == "host LONG and SHORT"


def test_terms_apply_before_builtin_patterns(run: Runner) -> None:
    # The address is a term, so it gets the term's label rather than EMAIL.
    result = run("mail jane@example.com", terms="jane@example.com => CONTACT\n")
    assert result.out == "mail CONTACT"


def test_comments_and_blank_lines_are_ignored(run: Runner) -> None:
    terms = "# a comment\n\n   \n  # indented comment\nsecret1 => ONE\n"
    assert run("secret1 # a comment", terms=terms).out == "ONE # a comment"


def test_label_with_backslash_is_inserted_literally(run: Runner) -> None:
    assert run("a secret b", terms="secret => C:\\work\\1\n").out == "a C:\\work\\1 b"


def test_crlf_and_byte_order_mark_in_the_terms_file(run: Runner) -> None:
    terms = b"\xef\xbb\xbfalpha => A\r\nbeta => B\r\n"
    assert run("alpha beta", terms=terms).out == "A B"


def test_terms_file_may_be_empty(run: Runner) -> None:
    result = run("nothing here", terms="")
    assert (result.out, result.err) == ("nothing here", "")


def test_missing_terms_file_warns_once_on_stderr(run: Runner) -> None:
    result = run("mail jane@example.com", terms=None)
    assert result.out == "mail EMAIL"  # built-in patterns still apply
    assert result.code == 0
    assert result.err.count("\n") == 1
    assert result.err.startswith("paste-redact: warning: terms file not found: ")
    assert str(run.terms_file) in result.err


def test_default_terms_file_is_under_home(run: Runner, tmp_path: Path) -> None:
    terms_dir = tmp_path / ".config" / "paste-redact"
    terms_dir.mkdir(parents=True)
    (terms_dir / "terms.txt").write_text("hunter2 => PASSWORD\n")
    result = run("pw hunter2", terms=None, env={"PASTE_REDACT_TERMS": ""})
    assert (result.out, result.err) == ("pw PASSWORD", "")


def test_unset_env_variable_uses_the_default_path(run: Runner, tmp_path: Path) -> None:
    terms_dir = tmp_path / ".config" / "paste-redact"
    terms_dir.mkdir(parents=True)
    (terms_dir / "terms.txt").write_text("hunter2 => PASSWORD\n")
    result = run("pw hunter2", terms=None, env={"PASTE_REDACT_TERMS": None})
    assert (result.out, result.err) == ("pw PASSWORD", "")


def test_missing_default_terms_file_names_the_default_path(
    run: Runner, tmp_path: Path
) -> None:
    result = run("x", terms=None, env={"PASTE_REDACT_TERMS": ""})
    assert f"{tmp_path}/.config/paste-redact/terms.txt" in result.err


def test_env_variable_overrides_the_default(run: Runner, tmp_path: Path) -> None:
    default_dir = tmp_path / ".config" / "paste-redact"
    default_dir.mkdir(parents=True)
    (default_dir / "terms.txt").write_text("hunter2=FROM_DEFAULT\n")
    assert (
        run("hunter2 swordfish", terms="swordfish => FROM_ENV\n").out
        == "hunter2 FROM_ENV"
    )


def test_unreadable_terms_file_stops_without_printing_the_text(run: Runner) -> None:
    # A directory where the file should be: carrying on would leak the secrets.
    run.terms_file.mkdir()
    result = run("secret text", terms=None)
    assert result.code != 0
    assert result.out == ""
    assert "cannot read terms file" in result.err


def test_terms_file_with_invalid_utf8_stops_without_printing_the_text(
    run: Runner,
) -> None:
    result = run("secret text", terms=b"caf\xe9 => X\n")
    assert result.code != 0
    assert result.out == ""
    assert "cannot read terms file" in result.err


def test_invalid_utf8_input_is_replaced_with_a_warning(run: Runner) -> None:
    result = run(b"ok \xff\xfe 111122223333 caf\xc3\xa9\n")
    assert result.out == "ok \ufffd\ufffd ACCOUNT caf\u00e9\n"
    assert result.code == 0
    assert "not valid UTF-8" in result.err
    assert result.err.count("\n") == 1


def test_valid_utf8_input_gives_no_warning(run: Runner) -> None:
    # U+FFFD in valid input is not a decoding problem.
    result = run("already \ufffd here")
    assert (result.out, result.err) == ("already \ufffd here", "")


def test_invalid_utf8_cannot_hide_a_term(run: Runner) -> None:
    assert run(b"\xff secret", terms="secret => S\n").out == "\ufffd S"


def test_version(run: Runner) -> None:
    result = run("", args=("--version",))
    assert result.out.startswith("paste-redact ")
    assert result.err == ""
    assert result.code == 0


def test_help_describes_the_tool_and_needs_no_terms_file(run: Runner) -> None:
    result = run("", terms=None, args=("--help",))
    assert result.code == 0
    assert "PASTE_REDACT_TERMS" in result.out
    assert result.err == ""


def test_no_other_options_exist(run: Runner) -> None:
    result = run("text", args=("--output", "file"))
    assert result.code == 2
    assert result.out == ""
    assert "unrecognized arguments" in result.err


def test_a_file_name_argument_is_an_error(run: Runner) -> None:
    result = run("text", args=(str(SCRIPT),))
    assert result.code == 2
    assert result.out == ""
