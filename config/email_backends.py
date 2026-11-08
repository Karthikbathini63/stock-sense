"""
Email backends for StockSense.

BrevoEmailBackend sends Django EmailMessage objects over Brevo's HTTPS
API (https://developers.brevo.com/reference/sendtransactionalemail).

This exists because serverless hosts such as Vercel block outbound SMTP
ports (25/465/587), which makes SMTP-only backends unusable in that
environment. The backend activates only when BREVO_API_KEY is set;
otherwise settings falls back to the standard SMTP backend.
"""

import json
import logging
import urllib.error
import urllib.request

from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoEmailBackend(BaseEmailBackend):

    def send_messages(self, email_messages):
        api_key = self._get_api_key()
        if not api_key:
            if self.fail_silently:
                return 0
            raise RuntimeError(
                "BREVO_API_KEY is not set; cannot send email via Brevo."
            )

        sent = 0

        for message in email_messages:
            try:
                self._post(api_key, message)
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception("Brevo send failed for %s", message.subject)

        return sent

    def _get_api_key(self):
        import os

        return os.environ.get("BREVO_API_KEY")

    def _post(self, api_key, message):
        payload = {
            "sender": {"email": message.from_email},
            "to": [{"email": address} for address in message.to],
            "subject": message.subject,
        }

        body_text = message.body or ""

        if message.content_subtype == "html":
            payload["htmlContent"] = body_text
        else:
            payload["textContent"] = body_text

        if message.cc:
            payload["cc"] = [{"email": a} for a in message.cc]
        if message.bcc:
            payload["bcc"] = [{"email": a} for a in message.bcc]
        if message.reply_to:
            payload["replyTo"] = {"email": message.reply_to[0]}

        request = urllib.request.Request(
            BREVO_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "accept": "application/json",
                "api-key": api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status not in (200, 201, 202):
                    body = response.read().decode("utf-8", "replace")
                    raise RuntimeError(
                        f"Brevo API returned {response.status}: {body[:200]}"
                    )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            # Do not leak the API key in error text.
            body = body.replace(api_key, "***")
            raise RuntimeError(
                f"Brevo API error {exc.code}: {body[:200]}"
            ) from exc
