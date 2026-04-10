"""Email adapter for AINL programs.

Fully-featured email support including:
- Send/receive with SMTP/IMAP
- HTML email with plain text fallback
- Attachments (send/receive)
- Reply with proper threading headers
- Draft management via IMAP
- OAuth support (future: requires provider-specific flows)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import smtplib
import imaplib
import email as email_lib
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email import encoders
from email.utils import make_msgid, formatdate
from typing import Any, Dict, List, Optional

from runtime.adapters.base import RuntimeAdapter, AdapterError

logger = logging.getLogger(__name__)


class EmailAdapter(RuntimeAdapter):
    """Fully-featured email adapter with SMTP/IMAP support.

    Environment variables:
    - EMAIL_SMTP_HOST: SMTP server (default: smtp.gmail.com)
    - EMAIL_SMTP_PORT: SMTP port (default: 587)
    - EMAIL_IMAP_HOST: IMAP server (default: imap.gmail.com)
    - EMAIL_IMAP_PORT: IMAP port (default: 993)
    - EMAIL_USERNAME: Email account username
    - EMAIL_PASSWORD: Email account password (use app-specific password)
    - EMAIL_FROM: Default sender address (defaults to EMAIL_USERNAME)
    - EMAIL_DRAFTS_FOLDER: Draft folder name (default: Drafts)
    """

    def __init__(self):
        self.smtp_host = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
        self.imap_host = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com")
        self.imap_port = int(os.getenv("EMAIL_IMAP_PORT", "993"))
        self.username = os.getenv("EMAIL_USERNAME", "")
        self.password = os.getenv("EMAIL_PASSWORD", "")
        self.from_addr = os.getenv("EMAIL_FROM", self.username)
        self.drafts_folder = os.getenv("EMAIL_DRAFTS_FOLDER", "Drafts")

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        """Dispatch email operations."""

        if target == "send":
            return self._send(args, context)
        elif target == "read":
            return self._read(args, context)
        elif target == "search":
            return self._search(args, context)
        elif target == "reply":
            return self._reply(args, context)
        elif target == "draft":
            return self._draft(args, context)
        elif target == "G":
            # Legacy OpenClaw target
            return self._read([], context)
        else:
            raise AdapterError(f"email adapter: unknown target '{target}'")

    def _send(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Send an email with full HTML and attachment support.

        Args:
            args[0]: to (recipient email address)
            args[1]: subject
            args[2]: body (plain text or dict with html/text keys)
            args[3]: cc (optional, comma-separated)
            args[4]: bcc (optional, comma-separated)
            args[5]: provider (optional, for future use)
            args[6]: attachments (optional, list of file paths or dicts)
        """
        if len(args) < 3:
            raise AdapterError("email.send requires at least 3 args: to, subject, body")

        to_addr = str(args[0])
        subject = str(args[1])
        body = args[2]
        cc = str(args[3]) if len(args) > 3 and args[3] else None
        bcc = str(args[4]) if len(args) > 4 and args[4] else None
        provider = str(args[5]) if len(args) > 5 and args[5] else None
        attachments = args[6] if len(args) > 6 else []

        if not self.username or not self.password:
            raise AdapterError(
                "email.send requires EMAIL_USERNAME and EMAIL_PASSWORD environment variables. "
                "For Gmail, use an app-specific password: https://myaccount.google.com/apppasswords"
            )

        try:
            # Create message
            msg = MIMEMultipart('mixed')
            msg['From'] = self.from_addr
            msg['To'] = to_addr
            msg['Subject'] = subject
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid()

            if cc:
                msg['Cc'] = cc
            if bcc:
                msg['Bcc'] = bcc

            # Handle body (HTML + plain text or just plain text)
            if isinstance(body, dict):
                # HTML email with plain text fallback
                msg_alternative = MIMEMultipart('alternative')
                msg.attach(msg_alternative)

                plain_text = body.get('text', '')
                html_text = body.get('html', '')

                if plain_text:
                    msg_alternative.attach(MIMEText(plain_text, 'plain', 'utf-8'))
                if html_text:
                    msg_alternative.attach(MIMEText(html_text, 'html', 'utf-8'))
            else:
                # Plain text only
                msg.attach(MIMEText(str(body), 'plain', 'utf-8'))

            # Handle attachments
            if attachments:
                for attachment in (attachments if isinstance(attachments, list) else [attachments]):
                    self._attach_file(msg, attachment)

            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)

                recipients = [to_addr]
                if cc:
                    recipients.extend([addr.strip() for addr in cc.split(',')])
                if bcc:
                    recipients.extend([addr.strip() for addr in bcc.split(',')])

                server.sendmail(self.from_addr, recipients, msg.as_string())

            logger.info(f"Email sent to {to_addr}: {subject}")

            return {
                "status": "sent",
                "provider": provider or "smtp",
                "method": "smtp",
                "to": to_addr,
                "subject": subject,
                "message_id": msg['Message-ID'],
                "attachments": len(attachments) if isinstance(attachments, list) else (1 if attachments else 0)
            }

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise AdapterError(f"email.send failed: {e}")

    def _attach_file(self, msg: MIMEMultipart, attachment: Any) -> None:
        """Attach a file to the email message.

        Args:
            attachment: File path (string) or dict with {path, filename, content, content_type}
        """
        if isinstance(attachment, str):
            # Simple file path
            file_path = attachment
            filename = os.path.basename(file_path)
        elif isinstance(attachment, dict):
            # Detailed attachment specification
            file_path = attachment.get('path')
            filename = attachment.get('filename', os.path.basename(file_path) if file_path else 'attachment')
            content = attachment.get('content')
            content_type = attachment.get('content_type')
        else:
            raise AdapterError(f"Invalid attachment format: {type(attachment)}")

        # Read file content
        if isinstance(attachment, dict) and 'content' in attachment:
            # Content provided directly (base64 or raw bytes)
            if isinstance(content, str):
                file_data = base64.b64decode(content)
            else:
                file_data = content
        elif file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                file_data = f.read()
        else:
            raise AdapterError(f"Attachment file not found: {file_path}")

        # Determine MIME type
        if isinstance(attachment, dict) and 'content_type' in attachment:
            maintype, subtype = content_type.split('/', 1)
        else:
            ctype, _ = mimetypes.guess_type(filename)
            if ctype is None:
                maintype, subtype = 'application', 'octet-stream'
            else:
                maintype, subtype = ctype.split('/', 1)

        # Create MIME part
        if maintype == 'text':
            part = MIMEText(file_data.decode('utf-8', errors='ignore'), subtype)
        elif maintype == 'image':
            part = MIMEImage(file_data, subtype)
        elif maintype == 'audio':
            part = MIMEAudio(file_data, subtype)
        else:
            part = MIMEBase(maintype, subtype)
            part.set_payload(file_data)
            encoders.encode_base64(part)

        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)

    def _read(self, args: List[Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Read emails from inbox with attachment extraction.

        Args:
            args[0]: folder (optional, default: INBOX)
            args[1]: limit (optional, default: 10)
            args[2]: unread_only (optional, default: true)
            args[3]: from_filter (optional)
            args[4]: subject_contains (optional)
            args[5]: include_attachments (optional, default: false)
        """
        folder = str(args[0]) if len(args) > 0 and args[0] else "INBOX"
        limit = int(args[1]) if len(args) > 1 and args[1] else 10
        unread_only = bool(args[2]) if len(args) > 2 and args[2] is not None else True
        from_filter = str(args[3]) if len(args) > 3 and args[3] else None
        subject_filter = str(args[4]) if len(args) > 4 and args[4] else None
        include_attachments = bool(args[5]) if len(args) > 5 else False

        if not self.username or not self.password:
            raise AdapterError(
                "email.read requires EMAIL_USERNAME and EMAIL_PASSWORD environment variables"
            )

        try:
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.username, self.password)
            mail.select(folder)

            # Build search criteria
            search_criteria = ["UNSEEN"] if unread_only else ["ALL"]
            if from_filter:
                search_criteria.append(f'FROM "{from_filter}"')
            if subject_filter:
                search_criteria.append(f'SUBJECT "{subject_filter}"')

            # Search for messages
            search_query = " ".join(search_criteria)
            _, message_numbers = mail.search(None, search_query)

            emails = []
            for num in message_numbers[0].split()[:limit]:
                _, msg_data = mail.fetch(num, "(RFC822)")
                email_body = msg_data[0][1]
                email_message = email_lib.message_from_bytes(email_body)

                # Extract body and attachments
                body_text = ""
                body_html = ""
                attachments = []

                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))

                    # Extract body
                    if content_type == "text/plain" and "attachment" not in content_disposition:
                        body_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif content_type == "text/html" and "attachment" not in content_disposition:
                        body_html = part.get_payload(decode=True).decode('utf-8', errors='ignore')

                    # Extract attachments
                    elif "attachment" in content_disposition and include_attachments:
                        filename = part.get_filename()
                        if filename:
                            attachments.append({
                                "filename": filename,
                                "content_type": content_type,
                                "size": len(part.get_payload(decode=False)),
                                "content": base64.b64encode(part.get_payload(decode=True)).decode('utf-8')
                            })

                email_dict = {
                    "id": num.decode(),
                    "from": email_message.get("From", ""),
                    "to": email_message.get("To", ""),
                    "subject": email_message.get("Subject", ""),
                    "body": body_text[:500] if not include_attachments else body_text,
                    "timestamp": email_message.get("Date", ""),
                    "unread": unread_only,
                    "message_id": email_message.get("Message-ID", ""),
                    "in_reply_to": email_message.get("In-Reply-To", ""),
                    "references": email_message.get("References", "")
                }

                if body_html:
                    email_dict["body_html"] = body_html[:500] if not include_attachments else body_html

                if attachments:
                    email_dict["attachments"] = attachments

                emails.append(email_dict)

            mail.close()
            mail.logout()

            logger.info(f"Read {len(emails)} emails from {folder}")
            return emails

        except Exception as e:
            logger.error(f"Failed to read emails: {e}")
            raise AdapterError(f"email.read failed: {e}")

    def _search(self, args: List[Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search emails using IMAP SEARCH syntax.

        Args:
            args[0]: query (IMAP search query)
            args[1]: limit (optional, default: 20)
            args[2]: folder (optional, default: INBOX)
        """
        if len(args) < 1:
            raise AdapterError("email.search requires at least 1 arg: query")

        query = str(args[0])
        limit = int(args[1]) if len(args) > 1 and args[1] else 20
        folder = str(args[2]) if len(args) > 2 and args[2] else "INBOX"

        if not self.username or not self.password:
            raise AdapterError(
                "email.search requires EMAIL_USERNAME and EMAIL_PASSWORD environment variables"
            )

        try:
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.username, self.password)
            mail.select(folder)

            _, message_numbers = mail.search(None, query)

            emails = []
            for num in message_numbers[0].split()[:limit]:
                _, msg_data = mail.fetch(num, "(RFC822)")
                email_body = msg_data[0][1]
                email_message = email_lib.message_from_bytes(email_body)

                # Extract snippet (first 100 chars of body)
                snippet = ""
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        snippet = body[:100]
                        break

                emails.append({
                    "id": num.decode(),
                    "from": email_message.get("From", ""),
                    "to": email_message.get("To", ""),
                    "subject": email_message.get("Subject", ""),
                    "snippet": snippet,
                    "timestamp": email_message.get("Date", ""),
                    "message_id": email_message.get("Message-ID", "")
                })

            mail.close()
            mail.logout()

            logger.info(f"Search found {len(emails)} emails")
            return emails

        except Exception as e:
            logger.error(f"Failed to search emails: {e}")
            raise AdapterError(f"email.search failed: {e}")

    def _reply(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Reply to an email with proper threading headers.

        Args:
            args[0]: message_id (original message ID to reply to)
            args[1]: body (reply text or dict with html/text)
            args[2]: reply_all (optional, default: false)
            args[3]: attachments (optional)
        """
        if len(args) < 2:
            raise AdapterError("email.reply requires at least 2 args: message_id, body")

        original_message_id = str(args[0])
        body = args[1]
        reply_all = bool(args[2]) if len(args) > 2 else False
        attachments = args[3] if len(args) > 3 else []

        if not self.username or not self.password:
            raise AdapterError("email.reply requires EMAIL_USERNAME and EMAIL_PASSWORD")

        try:
            # Fetch original message to get headers
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.username, self.password)
            mail.select("INBOX")

            # Search for original message by Message-ID
            _, message_numbers = mail.search(None, f'HEADER Message-ID "{original_message_id}"')

            if not message_numbers[0]:
                raise AdapterError(f"Original message not found: {original_message_id}")

            # Fetch original message
            num = message_numbers[0].split()[0]
            _, msg_data = mail.fetch(num, "(RFC822)")
            original_email = email_lib.message_from_bytes(msg_data[0][1])

            mail.close()
            mail.logout()

            # Extract original headers
            original_from = original_email.get("From", "")
            original_to = original_email.get("To", "")
            original_cc = original_email.get("Cc", "")
            original_subject = original_email.get("Subject", "")
            original_references = original_email.get("References", "")

            # Build reply subject
            reply_subject = original_subject
            if not reply_subject.lower().startswith("re:"):
                reply_subject = f"Re: {reply_subject}"

            # Build recipient list
            # Reply-To takes precedence over From
            reply_to = original_email.get("Reply-To", original_from)

            if reply_all:
                # Reply to all recipients
                all_recipients = set()
                all_recipients.add(reply_to)

                # Add original To recipients (except ourselves)
                if original_to:
                    for addr in original_to.split(','):
                        addr = addr.strip()
                        if addr and addr != self.from_addr:
                            all_recipients.add(addr)

                # Add original Cc recipients (except ourselves)
                if original_cc:
                    for addr in original_cc.split(','):
                        addr = addr.strip()
                        if addr and addr != self.from_addr:
                            all_recipients.add(addr)

                to_addr = ', '.join(all_recipients)
                cc = None
            else:
                # Reply only to sender
                to_addr = reply_to
                cc = None

            # Build References header for threading
            references = original_message_id
            if original_references:
                references = f"{original_references} {original_message_id}"

            # Create reply message
            msg = MIMEMultipart('mixed')
            msg['From'] = self.from_addr
            msg['To'] = to_addr
            msg['Subject'] = reply_subject
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid()
            msg['In-Reply-To'] = original_message_id
            msg['References'] = references

            if cc:
                msg['Cc'] = cc

            # Handle body (HTML + plain text or just plain text)
            if isinstance(body, dict):
                msg_alternative = MIMEMultipart('alternative')
                msg.attach(msg_alternative)

                plain_text = body.get('text', '')
                html_text = body.get('html', '')

                if plain_text:
                    msg_alternative.attach(MIMEText(plain_text, 'plain', 'utf-8'))
                if html_text:
                    msg_alternative.attach(MIMEText(html_text, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(str(body), 'plain', 'utf-8'))

            # Handle attachments
            if attachments:
                for attachment in (attachments if isinstance(attachments, list) else [attachments]):
                    self._attach_file(msg, attachment)

            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)

                recipients = [addr.strip() for addr in to_addr.split(',')]
                if cc:
                    recipients.extend([addr.strip() for addr in cc.split(',')])

                server.sendmail(self.from_addr, recipients, msg.as_string())

            logger.info(f"Reply sent to {to_addr}: {reply_subject}")

            return {
                "status": "sent",
                "provider": "smtp",
                "method": "reply",
                "to": to_addr,
                "subject": reply_subject,
                "message_id": msg['Message-ID'],
                "in_reply_to": original_message_id,
                "reply_all": reply_all
            }

        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            raise AdapterError(f"email.reply failed: {e}")

    def _draft(self, args: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update email draft using IMAP APPEND.

        Args:
            args[0]: to (recipient address)
            args[1]: subject
            args[2]: body (text or dict with html/text)
            args[3]: draft_id (optional, IMAP UID of existing draft to replace)
            args[4]: provider (optional)
        """
        if len(args) < 3:
            raise AdapterError("email.draft requires at least 3 args: to, subject, body")

        to_addr = str(args[0])
        subject = str(args[1])
        body = args[2]
        draft_id = str(args[3]) if len(args) > 3 and args[3] else None
        provider = str(args[4]) if len(args) > 4 and args[4] else None

        if not self.username or not self.password:
            raise AdapterError("email.draft requires EMAIL_USERNAME and EMAIL_PASSWORD")

        try:
            # Create draft message
            msg = MIMEMultipart('mixed')
            msg['From'] = self.from_addr
            msg['To'] = to_addr
            msg['Subject'] = subject
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid()

            # Handle body
            if isinstance(body, dict):
                msg_alternative = MIMEMultipart('alternative')
                msg.attach(msg_alternative)

                plain_text = body.get('text', '')
                html_text = body.get('html', '')

                if plain_text:
                    msg_alternative.attach(MIMEText(plain_text, 'plain', 'utf-8'))
                if html_text:
                    msg_alternative.attach(MIMEText(html_text, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(str(body), 'plain', 'utf-8'))

            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.username, self.password)

            # If updating existing draft, delete old version
            if draft_id:
                mail.select(self.drafts_folder)
                mail.store(draft_id, '+FLAGS', '\\Deleted')
                mail.expunge()

            # Append new draft to Drafts folder
            # Note: \Draft flag marks it as a draft
            mail.append(
                self.drafts_folder,
                '\\Draft',
                imaplib.Time2Internaldate(),
                msg.as_bytes()
            )

            # Get the UID of the newly created draft
            mail.select(self.drafts_folder)
            _, data = mail.search(None, 'ALL')
            draft_uids = data[0].split()
            new_draft_id = draft_uids[-1].decode() if draft_uids else None

            mail.close()
            mail.logout()

            logger.info(f"Draft created/updated: {subject}")

            return {
                "status": "draft_saved",
                "draft_id": new_draft_id,
                "to": to_addr,
                "subject": subject,
                "message_id": msg['Message-ID'],
                "folder": self.drafts_folder
            }

        except Exception as e:
            logger.error(f"Failed to create draft: {e}")
            raise AdapterError(f"email.draft failed: {e}")
