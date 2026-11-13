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
is `127.0.0.1:8088`; the runtime network is internal. The fixed credentials below
are for this local, synthetic-data demo only.

## Start the trial

Run these commands in a new directory. They work in a normal terminal, including
PowerShell when Docker Desktop is running Linux containers.

```sh
git clone --branch mail-links-trial-20261113 --depth 1 https://github.com/ArmyWas/paperless-ngx.git paperless-mail-links-demo
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
builds this container and executes the same import check on a Linux runner.
