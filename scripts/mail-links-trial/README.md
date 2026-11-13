# Try native links between documents from one email

AI disclosure: these trial files and the experimental implementation were written
by Codex, an AI assistant, with ArmyWas's authorization. No independent human
review is claimed. This is an experimental fork, not an accepted Paperless-ngx
release; upstream PR #14751 is closed.

This disposable demo builds Paperless from source and imports synthetic mail
through a local SMTP/IMAP server. It exercises the real mail importer and task
worker, then leaves the documents in the web UI for you to inspect. It does not
connect to your mailbox or mount an existing Paperless installation.

## Requirements

- Git, Docker with Linux containers, and Docker Compose v2 with `--wait` support.
- Internet access for the initial source/image/dependency downloads. Building the
  full application takes time and several GB of disk space.
- Port 8088 available on the computer running Docker. Use the browser on that
  computer; on a remote server, use an SSH tunnel instead of changing the bind
  address.

The supported first trial is a fresh instance. Do not replace a production image
or copy its volumes into this demo. All four storage volumes belong to the
explicit `paperless-mail-links-trial` Compose project. The only published port
is `127.0.0.1:8088`, published by a small browser proxy. The application, mailbox,
broker and parsing services remain on an internal network. Only the proxy also
connects to a normal bridge network and has outbound connectivity. The fixed
credentials below are for this local, synthetic-data demo only.

## Start the trial

Run these commands in a new directory. They work in a normal terminal, including
PowerShell when Docker Desktop is running Linux containers.

```sh
git clone --branch mail-links-trial-20261113-access1 --depth 1 https://github.com/ArmyWas/paperless-ngx.git paperless-mail-links-demo
cd paperless-mail-links-demo/scripts/mail-links-trial
docker compose -p paperless-mail-links-trial -f compose.yaml up -d --build --wait --wait-timeout 300
docker compose -p paperless-mail-links-trial -f compose.yaml exec -T webserver python3 /trial/smoke.py
```

The last command creates the test account, rules, custom field and sample mail
inside this disposable instance. It fails with a nonzero exit code if the expected
imports or links do not appear. Leave the terminal output available while checking
the UI. If any command fails, stop there rather than following the next step.

## Inspect the result

Open <http://127.0.0.1:8088> and sign in with username `trial` and password
`mail-links-local-trial`.

1. Open **Mail** and inspect the trial rules. The new **Link documents from the
   same email** setting selects a Document Link custom field. It is optional;
   existing rules default to no automatic linking.
2. Open the imported documents and their custom fields. The attachments-only
   example should contain separate A, B and C documents: A links to B, B links
   to both A and C, and C links to B. **A must not link to C.** B was the identical
   attachment in two different messages. This demo explicitly sets
   `PAPERLESS_CONSUMER_DELETE_DUPLICATES=true` so the importer reuses the existing
   document for a duplicate attachment; without that option, Paperless can create
   additional documents for the same bytes.
3. In the full-email example, the email and its two attachments should remain
   three separate documents, with links to the other two. Open the original-file
   download for the email to inspect the EML source.

These are links between documents, not a permanent per-message identifier. The
feature does not merge files, infer relations in old imports, or combine separate
mail-rule batches. This first trial checks an isolated SQLite deployment with
synthetic mail; it does not establish compatibility with your provider, rules,
permissions, or existing database.

Please report whether installation completed, whether the links above were
correct, and whether this native setting fits the task you described. If setup
is impractical, say which part blocked you and what deployment you use. Do not
post private mail, passwords or a full environment dump. Actual use on your own
mail is a separate next step after this disposable trial.

## Troubleshooting and cleanup

### Existing trial starts, but the browser cannot connect

The original `mail-links-trial-20261113` tag requested a host port on an
internal-only network. The application could pass its internal health and import
checks while no browser port was published. The `access1` revision adds a local
proxy and checks the host entry separately.

For an existing trial in **WSL/Linux**, run the following from its original
`scripts/mail-links-trial` directory. Stop if any command fails:

```sh
git fetch origin tag mail-links-trial-20261113-access1
git show mail-links-trial-20261113-access1:scripts/mail-links-trial/recover-access.sh > recover-access.sh
bash recover-access.sh
```

The recovery script checks the running trial's four named volumes before making
changes, keeps the existing application image and documents, and writes a separate
`compose.access-fixed.yaml`. Your original `compose.yaml` is left intact. If it
finds nonstandard mounts, it stops instead of attaching an empty database. It
downloads the small proxy image and may recreate the application container while
retaining all four volumes. It does not rebuild the application or re-import mail.

Use `-f compose.access-fixed.yaml` for subsequent start, stop and status commands
after recovery. Do **not** run the fresh-instance import command again or remove
volumes to fix browser access.

Open <http://127.0.0.1:8088> on the same computer. If it still does not open, run
these in the same WSL terminal and share the output:

```sh
docker compose -p paperless-mail-links-trial -f compose.access-fixed.yaml ps --all
curl --max-time 10 -I http://127.0.0.1:8088/accounts/login/
```

If WSL can reach the page but a Windows browser cannot, that separates a remaining
WSL forwarding problem from the container's port publication. Do not change the
binding to a public address or disable the firewall.

To check the already imported synthetic samples through the **host** entry, without
initializing or importing anything, optionally use Python 3.11 or newer:

```sh
git show mail-links-trial-20261113-access1:scripts/mail-links-trial/smoke.py > verify-access.py
python3 verify-access.py --verify-only --base-url http://127.0.0.1:8088
```

This checks the six documents, exact links, original PDF/EML contents and four
successful mail records. It only authenticates and reads the existing trial data.

### Status and cleanup

For a **recovered** trial, use the generated configuration:

```sh
docker compose -p paperless-mail-links-trial -f compose.access-fixed.yaml ps --all
docker compose -p paperless-mail-links-trial -f compose.access-fixed.yaml stop
```

The examples below use `compose.yaml` for a fresh checkout. After recovery, replace
it with `compose.access-fixed.yaml` in **every** command, including cleanup, so the
browser proxy is included.

To inspect this trial's services and recent logs:

```sh
docker compose -p paperless-mail-links-trial -f compose.yaml ps --all
docker compose -p paperless-mail-links-trial -f compose.yaml logs --tail=100 webserver greenmail
```

Stop the demo while keeping its imported documents:

```sh
docker compose -p paperless-mail-links-trial -f compose.yaml stop
```

Remove the demo and **delete its test documents and database**:

```sh
docker compose -p paperless-mail-links-trial -f compose.yaml down --volumes
```

The image and cloned source remain. Repeating `up` after removing the volumes
starts a fresh trial. Do not change the project name in the cleanup command.

The fork's [Mail links isolated trial workflow](../../.github/workflows/mail-links-trial.yml)
builds this container, executes the import check, and verifies the published host
entry and existing samples from a Linux runner. For a second independent local
test, `MAIL_LINKS_TRIAL_PORT` can select a different loopback port; the default is 8088. Do not change the project name of an existing trial.
