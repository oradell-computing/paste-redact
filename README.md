# paste-redact

Clean terminal output before you paste it into an AI chat, an issue or a forum.

`paste-redact` reads text on standard input and writes it to standard output with sensitive
values masked: AWS account IDs and access keys, private keys, long tokens, sign-in codes,
UUIDs, email addresses, IP addresses, and any private terms you list yourself. It is one
Python file with no dependencies, and nothing it reads leaves your machine.

```
$ cat deploy.log | paste-redact
role arn:aws:iam::ACCOUNT:role/deploy
contact EMAIL from IP
```

A longer example. Before:

```
Updated profile dev to use arn:aws:sts::111122223333:assumed-role/Admin/123e4567-e89b-12d3-a456-426614174000 credentials.
Contact jane@example.com from 192.0.2.10
```

After:

```
Updated profile dev to use arn:aws:sts::ACCOUNT:assumed-role/Admin/UUID credentials.
Contact EMAIL from IP
```

It is a safety net, not a guarantee: always read the result before you send it (see
[Limitations](#limitations)).

## Requirements

- Python 3.10 or newer, as `python3` on your `PATH`
- Linux, macOS, or Windows through WSL

## Install

The script is short. Read it before you run it.

```bash
git clone https://github.com/oradell-computing/paste-redact.git
cd paste-redact
mkdir -p ~/.local/bin ~/.config/paste-redact
install -m 755 paste_redact.py ~/.local/bin/paste-redact
touch ~/.config/paste-redact/terms.txt
chmod 600 ~/.config/paste-redact/terms.txt
command -v paste-redact && paste-redact --version
```

The last line should print the path and `paste-redact 0.1.0`. If it prints nothing, open a new
shell: most Linux distributions add `~/.local/bin` to your `PATH` once it exists.

**macOS:** add `export PATH="$HOME/.local/bin:$PATH"` to `~/.zshrc` and open a new terminal.
The `python3` that ships with Apple's command-line tools is usually 3.9, which is too old;
install a newer Python (for example from python.org or Homebrew) and check with
`python3 --version`.

**Updating:** pull the latest version and run the same `install` line again.

## Quick test

```bash
echo 'acct 111122223333 ip 192.0.2.10 mail jane@example.com' | paste-redact
```

Expected: `acct ACCOUNT ip IP mail EMAIL`.

## Your private terms

The built-in patterns can't know your client names, project names or machine details. List
them in your terms file:

```
~/.config/paste-redact/terms.txt
```

To use a different file, set `PASTE_REDACT_TERMS=/path/to/terms.txt`. An empty value counts as
unset.

The format is one entry per line:

```
# Lines starting with # are comments (a comment must be on its own line).

# secret => LABEL replaces the secret with your label
111122223333 => DEV_ACCOUNT
444455556666 => PROD_ACCOUNT
client.example.com => CLIENT_DOMAIN

# A line without " => " is masked as REDACTED, even if it contains "="
project-bluebird
DB_PASSWORD=hunter2
```

- Terms are literal text, matched without regard to case. The longest term wins when two
  overlap, and terms are applied before the built-in patterns.
- Spaces around the secret and the label are trimmed. Labels are inserted exactly as written.
- A plain line masks only that exact text. In the example above, `hunter2` on its own is not
  masked unless you list it on its own line too.
- Files saved by Windows editors (CRLF line endings, a byte-order mark) work as expected.

The terms file holds your real secrets. Keep it readable only by you (`chmod 600`), and never
put it inside a git repository. Edit it with an editor rather than `echo`, so the values don't
end up in your shell history.

## Usage

**A command that doesn't ask you anything:**

```bash
git log -3 2>&1 | paste-redact
```

`2>&1` includes error messages, which often contain the most revealing details.

**Several commands at once:**

```bash
{ aws sts get-caller-identity; aws s3 ls; } 2>&1 | paste-redact
```

**Into a file you can attach:**

```bash
{ cmd1; cmd2; } 2>&1 | paste-redact > ~/to-share.txt
```

**Anything interactive, already on screen, or on your clipboard:**

1. Run the command normally (or copy the text you want to share).
2. Run `paste-redact > ~/to-share.txt`.
3. Paste the text into the terminal, press **Enter**, then **Ctrl+D**.
4. Share `~/to-share.txt`.

Leave out `> ~/to-share.txt` to see the result on screen instead.

**Never pipe an interactive command** (a sign-in, a deploy that asks for confirmation, anything
waiting for input). `paste-redact` prints only after its input ends, so you would never see the
prompt or the sign-in link. Use the paste method above instead.

### Options

| Option | What it does |
| --- | --- |
| `--help` | Show a short usage message |
| `--version` | Show the version |

### Messages and exit codes

Messages go to standard error, never into the redacted output.

| Message | Meaning |
| --- | --- |
| `warning: terms file not found` | Only the built-in patterns were applied |
| `warning: input is not valid UTF-8` | Invalid bytes were replaced with `U+FFFD` and the rest was redacted |
| a warning about an empty secret | A line such as ` => LABEL` was ignored |
| `error: cannot read terms file` | The run stopped and printed **nothing**, rather than output that might still contain your terms |

Exit codes: `0` success, `1` the terms file couldn't be read, `2` an unknown option.

## What it masks

Built-in patterns run in this order, after your terms:

| Pattern | Replaced with |
| --- | --- |
| Sign-in values in URLs: `state=`, `code=`, `code_challenge=`, `code_verifier=` | `state=REDACTED` (and so on) |
| AWS access key IDs (`AKIA…`, `ASIA…`) | `ACCESS_KEY_ID` |
| AWS secret access keys after `secret_access_key` or `SecretAccessKey` | `SECRET_KEY` |
| Token-like strings of 100 or more characters | `LONG_TOKEN` |
| PEM private key blocks | `PRIVATE_KEY` |
| UUIDs | `UUID` |
| Exactly 12 digits (AWS account IDs, including inside ARNs) | `ACCOUNT` |
| Email addresses | `EMAIL` |
| IPv4 addresses, except `127.0.0.1` and `0.0.0.0` | `IP` |

## Notepad++ on Windows (through WSL)

You can run `paste-redact` from Notepad++ if it is installed in WSL as above.

1. Open **Run → Run…** (F5) and enter, replacing `<distro>` (for example `Ubuntu`) and
   `<user>` with your WSL distribution and username:

   ```
   cmd /c "wsl.exe -d <distro> -e /home/<user>/.local/bin/paste-redact < "$(FULL_CURRENT_PATH)" > "$(FULL_CURRENT_PATH).redacted.txt""
   ```

2. Click **Save…**, name it **paste-redact**, and choose a shortcut.
3. Paste your text into a tab, save it as UTF-8 (**Encoding → UTF-8**), and run the command.
   The redacted copy is written next to the file as `<name>.redacted.txt`.

Test it once with a line such as `acct 111122223333` before relying on it: you should get
`acct ACCOUNT`.

## Limitations

- **It only knows its patterns and your terms.** Names of people, clients and projects,
  hostnames, internal URLs, passwords and tokens from other services (most are shorter than
  100 characters) pass through unless you list them as terms.
- **The patterns are blunt.** Any 12 digits become `ACCOUNT`, including example IDs. A
  four-part version number such as `1.2.3.4` becomes `IP`. IPv6 addresses, 13-digit
  timestamps and 40-character git hashes are not masked.
- **Plain terms match exact text only**, so variations need their own lines.
- **It can't redact what you have already sent.** Clean the text first, then paste.

Read every result before you share it.

## Good habits

- If you pasted from the clipboard, the original is still there, and in your clipboard
  history if you use one (on Windows: **Win+V → Clear all**).
- Delete shared files when you're done: `rm ~/to-share.txt`.
- Your shell history records the command line, not the text you paste into it.

## Development

```bash
make install    # virtualenv with pytest and mypy (uses uv; Python 3.14 by default)
make check      # ruff, mypy, pytest and a 12-digit-number scan
```

`make install` only creates `.venv` if it doesn't exist yet. To test on the oldest supported
Python, delete it first, then switch back the same way:

```bash
rm -rf .venv && make install PYTHON_VERSION=3.10 && make check
rm -rf .venv && make install
```

The tests run the script as a separate process with its own temporary terms file, so your real
terms file is never read.

## Security

To report a security problem, see [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
