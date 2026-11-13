#!/usr/bin/env python3
"""Exercise the disposable Compose trial using only synthetic mail and public APIs.

AI-authored experimental-fork tooling, with ArmyWas's authorization. Initialize
inside the trial webserver container, or verify existing synthetic data through
a loopback host URL. This script has no real mailbox or production credentials.
"""

from __future__ import annotations

import argparse
import email.policy
import imaplib
import json
import smtplib
import sys
import time
from datetime import UTC
from datetime import datetime
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import format_datetime
from email.utils import make_msgid
from typing import Any
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.parse import urlsplit
from urllib.request import Request
from urllib.request import urlopen

API_BASE = "http://127.0.0.1:8000"
ADMIN_USER = "trial"
ADMIN_PASSWORD = "mail-links-local-trial"  # Disposable local demo credentials.
MAIL_HOST = "greenmail"
SMTP_PORT = 3025
IMAP_PORT = 3143
MAIL_USER = "trial@localhost"
MAIL_PASSWORD = "trial"  # Synthetic mailbox in the same isolated Compose network.
PREFIX = "Mail links trial"
BATCH_TIMEOUT = 180


def require(condition: bool, message: str) -> None:  # noqa: FBT001
    if not condition:
        raise RuntimeError(message)


def progress(message: str) -> None:
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


class Api:
    def __init__(self, base_url: str = API_BASE) -> None:
        origin = urlsplit(base_url)
        require(
            origin.scheme == "http"
            and origin.hostname in {"127.0.0.1", "localhost", "::1"}
            and origin.username is None
            and origin.password is None
            and origin.path in {"", "/"}
            and not origin.query
            and not origin.fragment
            and (origin.port is None or origin.port > 0),
            "The trial base URL must be an HTTP loopback origin without a path, "
            "credentials, query or fragment.",
        )
        self.base_url = base_url.rstrip("/")
        self.token = ""

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        binary: bool = False,
    ) -> Any:
        url = urljoin(self.base_url, path)
        require(
            (urlsplit(url).scheme, urlsplit(url).netloc)
            == (urlsplit(self.base_url).scheme, urlsplit(self.base_url).netloc),
            "Refusing an API request outside the disposable local server.",
        )
        headers = {"Accept": "application/json; version=10"}
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        payload = None
        if data is not None:
            payload = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=payload, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read()
        except HTTPError as error:
            # Do not print request headers, tokens, or authentication responses.
            raise RuntimeError(
                f"{method} {path} returned HTTP {error.code}.",
            ) from error
        return body if binary else json.loads(body) if body else None

    def login(self) -> None:
        deadline = time.monotonic() + 90
        while True:
            try:
                result = self.request(
                    "/api/token/",
                    method="POST",
                    data={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
                )
                self.token = result["token"]
                return
            except (RuntimeError, URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "The local trial API/login did not become ready.",
                    )
                time.sleep(2)

    def items(self, path: str) -> list[dict[str, Any]]:
        result = []
        while path:
            page = self.request(path)
            if isinstance(page, list):
                return result + page
            result.extend(page["results"])
            path = page.get("next")
        return result


def mailbox_uids() -> list[bytes]:
    with imaplib.IMAP4(MAIL_HOST, IMAP_PORT, timeout=20) as mailbox:
        mailbox.login(MAIL_USER, MAIL_PASSWORD)
        status, _ = mailbox.select("INBOX", readonly=True)
        require(status == "OK", "Cannot select the synthetic INBOX.")
        status, values = mailbox.uid("SEARCH", None, "ALL")
        require(status == "OK", "Cannot search the synthetic INBOX.")
        return values[0].split() if values and values[0] else []


def synthetic_pdf(label: str) -> bytes:
    """A tiny valid, text-based PDF; each label has stable, distinct bytes."""
    text = f"SYNTHETIC MAIL LINKS TRIAL - Document {label} - No customer data"
    content = f"BT /F1 16 Tf 40 780 Td ({text}) Tj ET\n".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, value in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + value + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode(),
    )
    return bytes(pdf)


def send_message(subject: str, attachments: dict[str, bytes]) -> None:
    message = EmailMessage(policy=email.policy.SMTP)
    message["From"] = "Synthetic Sender <sender@mail-links.invalid>"
    message["To"] = MAIL_USER
    message["Subject"] = subject
    message["Date"] = format_datetime(datetime.now(UTC))
    message["Message-ID"] = make_msgid(domain="mail-links.invalid")
    message.set_content(
        "SYNTHETIC BODY CONTEXT: these separate attachments arrived together.\n"
        "This message contains no private or customer information.\n",
    )
    for filename, payload in attachments.items():
        message.add_attachment(
            payload,
            maintype="application",
            subtype="pdf",
            filename=filename,
        )
    with smtplib.SMTP(MAIL_HOST, SMTP_PORT, timeout=20) as smtp:
        refused = smtp.send_message(message)
        require(not refused, "The local SMTP server rejected the synthetic recipient.")


def import_batch(
    api: Api,
    account_id: int,
    rule_id: int,
    subject: str,
    attachments: dict[str, bytes],
) -> None:
    require(
        not mailbox_uids(),
        "The synthetic mailbox must be empty before each batch.",
    )
    send_message(subject, attachments)
    deadline = time.monotonic() + 30
    while not mailbox_uids():
        require(time.monotonic() < deadline, "Synthetic SMTP delivery timed out.")
        time.sleep(1)
    api.request(f"/api/mail_accounts/{account_id}/process/", method="POST", data={})
    deadline = time.monotonic() + BATCH_TIMEOUT
    next_progress = time.monotonic() + 15
    while time.monotonic() < deadline:
        records = [
            record
            for record in api.items("/api/processed_mail/?page_size=100")
            if record["subject"] == subject and record["rule"] == rule_id
        ]
        require(
            not any(record["status"] == "FAILED" for record in records),
            f"Mail consumption failed for {subject!r}; inspect the trial service logs.",
        )
        if any(record["status"] == "SUCCESS" for record in records):
            require(
                not mailbox_uids(),
                "Processing reported SUCCESS but the DELETE mail action did not finish.",
            )
            progress(f"  Imported and completed mail action: {subject}")
            return
        if time.monotonic() >= next_progress:
            progress(f"  Waiting for native mail consumption: {subject}")
            next_progress = time.monotonic() + 15
        time.sleep(2)
    raise RuntimeError(f"Native consumption timed out for {subject!r}.")


def documents_by_filename(api: Api, expected_count: int) -> dict[str, dict[str, Any]]:
    documents = api.items("/api/documents/?page_size=100")
    require(
        len(documents) == expected_count,
        f"Expected {expected_count} documents, found {len(documents)}. "
        "Check that the disposable trial enables duplicate rejection.",
    )
    result = {document["original_file_name"]: document for document in documents}
    require(len(result) == len(documents), "Unexpected duplicate original filenames.")
    require(
        all(document.get("user_can_change") for document in documents),
        "The trial administrator cannot change every imported document.",
    )
    return result


def verify_links(
    documents: dict[str, dict[str, Any]],
    field_id: int,
    expected: dict[str, set[str]],
) -> None:
    require(set(documents) == set(expected), "Unexpected set of imported source files.")
    for filename, neighbours in expected.items():
        document = documents[filename]
        instances = [
            item for item in document["custom_fields"] if item["field"] == field_id
        ]
        require(len(instances) == 1, f"Missing or duplicate link field on {filename}.")
        expected_ids = {documents[name]["id"] for name in neighbours}
        actual_ids = instances[0]["value"]
        require(isinstance(actual_ids, list), f"Unexpected link value on {filename}.")
        require(
            set(actual_ids) == expected_ids and len(actual_ids) == len(expected_ids),
            f"Incorrect direct links on {filename}: expected {sorted(expected_ids)}, "
            f"found {actual_ids}.",
        )


def verify_completed_trial(api: Api, field_id: int) -> None:
    documents = documents_by_filename(api, 6)
    eml_name = f"{PREFIX} - full email DE.eml"
    expected = {
        "A.pdf": {"B.pdf"},
        "B.pdf": {"A.pdf", "C.pdf"},
        "C.pdf": {"B.pdf"},
        eml_name: {"D.pdf", "E.pdf"},
        "D.pdf": {eml_name, "E.pdf"},
        "E.pdf": {eml_name, "D.pdf"},
    }
    verify_links(documents, field_id, expected)
    payloads = {f"{label}.pdf": synthetic_pdf(label) for label in "ABCDE"}
    for name, payload in payloads.items():
        original = api.request(
            f"/api/documents/{documents[name]['id']}/download/?original=true",
            binary=True,
        )
        require(original == payload, f"The stored original bytes changed for {name}.")
    eml_document = documents[eml_name]
    require(
        eml_document["mime_type"] == "message/rfc822",
        "Full mail is not stored as EML.",
    )
    eml_bytes = api.request(
        f"/api/documents/{eml_document['id']}/download/?original=true",
        binary=True,
    )
    eml = BytesParser(policy=email.policy.default).parsebytes(eml_bytes)
    body = eml.get_body(preferencelist=("plain",))
    require(
        body is not None and "SYNTHETIC BODY CONTEXT" in body.get_content(),
        "The downloadable EML did not retain its synthetic body context.",
    )
    embedded = {
        part.get_filename(): part.get_payload(decode=True)
        for part in eml.iter_attachments()
    }
    require(
        embedded == {name: payloads[name] for name in ["D.pdf", "E.pdf"]},
        "The downloadable EML did not retain both exact original attachments.",
    )
    records = api.items("/api/processed_mail/?page_size=100")
    require(
        len(records) == 4 and all(record["status"] == "SUCCESS" for record in records),
        "Expected four successful native email batches.",
    )
    progress(
        "PASS: four successful mail records; six separate, intact source documents.",
    )
    progress(
        "PASS: A-B and B-C only; six documents with no extra links.",
    )
    progress(
        "PASS: full EML, D and E link symmetrically; original body/attachments preserved.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing synthetic trial data; do not import or change documents.",
    )
    parser.add_argument(
        "--base-url",
        default=API_BASE,
        help="HTTP loopback origin for --verify-only (default: %(default)s).",
    )
    args = parser.parse_args()
    require(
        args.verify_only or args.base_url == API_BASE,
        "A custom base URL is only supported with --verify-only. "
        "Initialize the trial inside its webserver container.",
    )
    api = Api(args.base_url)
    if args.verify_only:
        progress(f"Verifying existing synthetic trial data through {api.base_url}.")
        api.login()
        fields = [
            field
            for field in api.items("/api/custom_fields/")
            if field["name"] == f"{PREFIX} - Same email"
            and field["data_type"] == "documentlink"
        ]
        require(len(fields) == 1, "Expected exactly one synthetic trial link field.")
        verify_completed_trial(api, fields[0]["id"])
        progress("Verification finished without importing or changing trial documents.")
        return
    progress("Starting the isolated native mail-links trial (synthetic data only).")
    api.login()
    for resource in ["documents", "mail_accounts", "mail_rules", "processed_mail"]:
        require(
            not api.items(f"/api/{resource}/?page_size=100"),
            "This script requires a fresh disposable instance. It will not modify "
            f"an instance containing existing {resource}. See the trial cleanup instructions.",
        )
    require(not mailbox_uids(), "The disposable mail server already contains mail.")
    field_name = f"{PREFIX} - Same email"
    require(
        not any(
            field["name"] == field_name for field in api.items("/api/custom_fields/")
        ),
        "A previous trial's custom field exists. Start a fresh disposable instance.",
    )
    field = api.request(
        "/api/custom_fields/",
        method="POST",
        data={"name": field_name, "data_type": "documentlink"},
    )
    account = api.request(
        "/api/mail_accounts/",
        method="POST",
        data={
            "name": f"{PREFIX} - Local synthetic mailbox",
            "imap_server": MAIL_HOST,
            "imap_port": IMAP_PORT,
            "imap_security": 1,
            "account_type": 1,
            "username": MAIL_USER,
            "password": MAIL_PASSWORD,
            "character_set": "UTF-8",
            "is_token": False,
        },
    )
    rules = {}
    for name, scope in [("attachments", 1), ("full email", 3)]:
        rule = api.request(
            "/api/mail_rules/",
            method="POST",
            data={
                "name": f"{PREFIX} - {name}",
                "account": account["id"],
                "enabled": True,
                "folder": "INBOX",
                "filter_subject": f"{PREFIX} - {name}",
                "filter_attachment_filename_include": "*.pdf",
                "consumption_scope": scope,
                "attachment_type": 1,
                "assign_title_from": 2,
                "assign_owner_from_rule": True,
                "assign_document_link_field": field["id"],
                "action": 1,
                "stop_processing": True,
            },
        )
        require(
            rule.get("assign_document_link_field") == field["id"],
            "This build did not accept the native mail-link setting.",
        )
        rules[name] = rule["id"]

    payloads = {f"{label}.pdf": synthetic_pdf(label) for label in "ABCDE"}
    account_id, field_id = account["id"], field["id"]
    attachments_rule = rules["attachments"]
    for suffix, names, count in [
        ("AB", ["A.pdf", "B.pdf"], 2),
        ("BC", ["B.pdf", "C.pdf"], 3),
        ("AB duplicate replay", ["A.pdf", "B.pdf"], 3),
    ]:
        import_batch(
            api,
            account_id,
            attachments_rule,
            f"{PREFIX} - attachments {suffix}",
            {name: payloads[name] for name in names},
        )
        documents = documents_by_filename(api, count)
        expected = {"A.pdf": {"B.pdf"}, "B.pdf": {"A.pdf"}}
        if count == 3:
            expected["B.pdf"].add("C.pdf")
            expected["C.pdf"] = {"B.pdf"}
        verify_links(documents, field_id, expected)
        progress(f"  Verified {count} separate documents and exact symmetric links.")

    full_subject = f"{PREFIX} - full email DE"
    import_batch(
        api,
        account_id,
        rules["full email"],
        full_subject,
        {name: payloads[name] for name in ["D.pdf", "E.pdf"]},
    )
    verify_completed_trial(api, field_id)
    progress("The synthetic documents remain at http://127.0.0.1:8088 for inspection.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.stderr.write(f"FAIL: {error}\n")
        sys.stderr.flush()
        sys.exit(1)
