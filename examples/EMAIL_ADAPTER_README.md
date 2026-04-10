# Email Adapter Examples

This directory contains example AINL programs demonstrating the `email` adapter for sending, reading, and processing emails.

## Overview

The `email` adapter provides five operations:

| Target | Description | Arguments | Returns |
|--------|-------------|-----------|---------|
| `send` | Send an email | to, subject, body, [cc], [bcc], [provider], [attachments] | `{status, provider, method, to, subject, message_id, attachments}` |
| `read` | Read emails from inbox | [folder], [limit], [unread_only], [from], [subject_contains], [include_attachments] | `[{id, from, to, subject, body, timestamp, unread, message_id, attachments}]` |
| `search` | Search emails | query, [limit], [folder] | `[{id, from, to, subject, snippet, timestamp, message_id}]` |
| `reply` | Reply to email with threading | message_id, body, [reply_all], [attachments] | `{status, to, subject, message_id, in_reply_to, reply_all}` |
| `draft` | Create/update draft | to, subject, body, [draft_id], [provider] | `{status, draft_id, to, subject, message_id, folder}` |

## Configuration

### Environment Variables

The email adapter requires the following environment variables:

```bash
# SMTP Configuration (for sending)
export EMAIL_SMTP_HOST=smtp.gmail.com
export EMAIL_SMTP_PORT=587

# IMAP Configuration (for reading)
export EMAIL_IMAP_HOST=imap.gmail.com
export EMAIL_IMAP_PORT=993

# Credentials
export EMAIL_USERNAME=your.email@gmail.com
export EMAIL_PASSWORD=your_app_specific_password
export EMAIL_FROM=your.email@gmail.com  # Optional, defaults to EMAIL_USERNAME
```

### Gmail App-Specific Passwords

For Gmail, you **must** use an app-specific password (not your regular password):

1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and your device
3. Copy the generated 16-character password
4. Use this as your `EMAIL_PASSWORD`

### Other Email Providers

| Provider | SMTP Host | IMAP Host |
|----------|-----------|-----------|
| **Gmail** | smtp.gmail.com:587 | imap.gmail.com:993 |
| **Outlook** | smtp.office365.com:587 | outlook.office365.com:993 |
| **Yahoo** | smtp.mail.yahoo.com:587 | imap.mail.yahoo.com:993 |
| **FastMail** | smtp.fastmail.com:587 | imap.fastmail.com:993 |
| **iCloud** | smtp.mail.me.com:587 | imap.mail.me.com:993 |

### Adapter Allowlist

Add `email` to your adapter allowlist:

```bash
# Option 1: Explicit allowlist
export AINL_HOST_ADAPTER_ALLOWLIST=core,http,email

# Option 2: Allow all IR-declared adapters (recommended)
export AINL_ALLOW_IR_DECLARED_ADAPTERS=1
```

## Examples

### 1. Send Email (`email_send_example.ainl`)

Send a simple notification email:

```ainl
R email.send "recipient@example.com" "Test Subject" "Hello from AINL!" ->res
J res
```

### 2. Read Emails (`email_read_example.ainl`)

Read the 5 most recent unread emails:

```ainl
R email.read "INBOX" 5 true ->emails
R core.LEN emails ->count
J {"email_count": count, "emails": emails}
```

### 3. Auto-Responder (`email_autoresponder.ainl`)

Automatically respond to unread emails:

```ainl
R email.read "INBOX" 10 true ->emails
R core.GET [0] emails ->first
R core.GET ["from"] first ->sender
R email.send sender "Re: Your message" "Thanks for your email!" ->res
```

### 4. Email Search

Search for emails from a specific sender:

```ainl
# IMAP search syntax
R email.search 'FROM "alerts@example.com"' 20 "INBOX" ->results
```

### 5. Reply with Threading (`email_reply_example.ainl`)

Reply to an email with proper threading headers:

```ainl
# Read the most recent email
R email.read "INBOX" 1 true ->emails
R core.GET [0] emails ->first_email
R core.GET ["message_id"] first_email ->msg_id

# Reply with threading (sets In-Reply-To and References headers)
R email.reply msg_id "Thank you for your email!" false ->reply_result
```

### 6. Create Draft (`email_draft_example.ainl`)

Save an email as a draft without sending:

```ainl
# Create draft in Drafts folder
R email.draft "recipient@example.com" "Project Update - DRAFT" "Draft content here..." ->draft
R core.GET ["draft_id"] draft ->draft_id
```

### 7. HTML Email (`email_html_example.ainl`)

Send formatted HTML email with plain text fallback:

```ainl
# Create HTML version
S html "<html><body><h1>Hello!</h1><p>This is <strong>formatted</strong>!</p></body></html>"
S plain "Hello!\n\nThis is formatted!"

# Create body dict
R core.SET_MULTI ["text", "html"] [plain, html] {} ->body
R email.send "recipient@example.com" "Formatted Email" body ->result
```

### 8. Email with Attachments (`email_attachment_example.ainl`)

Send an email with file attachments:

```ainl
# Create attachment list (file paths)
R core.LIST "/tmp/report.pdf" ->attachments

# Send with attachment (7th argument)
R email.send "recipient@example.com" "Monthly Report" "See attached." "" "" "" attachments ->result
```

**Search Query Syntax (IMAP):**
- `FROM "user@example.com"` - From specific sender
- `SUBJECT "meeting"` - Subject contains keyword
- `UNSEEN` - Unread emails only
- `SINCE "01-Jan-2024"` - After date
- Combine with spaces: `FROM "boss@example.com" UNSEEN`

## Integration with ArmaraOS

When running AINL programs through ArmaraOS agents:

1. **Scheduled AINL** - The email adapter will use environment variables from the ArmaraOS daemon process
2. **Agent Tools** - For advanced features (reply with threading, draft management), use ArmaraOS `email_send` / `email_read` tools instead
3. **MCP Integration** - ArmaraOS email tools support MCP servers (Gmail, Outlook) with OAuth - the AINL adapter does not yet support this

### Recommended Pattern

For **simple automations** (send notification, read inbox count):
```ainl
# Use email adapter directly
R email.send "admin@example.com" "Alert" "System status OK" ->res
```

For **complex email workflows** (threading, drafts, OAuth):
```python
# Use ArmaraOS agent with email tools
# Agent can call email_send, email_reply, email_draft with full MCP support
```

## Capabilities

### ✅ Fully Implemented

1. **Email Threading** - Full reply support with In-Reply-To and References headers
   - Automatically fetches original message
   - Maintains conversation threading
   - Reply-all option supported

2. **Draft Management** - IMAP-based draft creation/updating
   - Save drafts to Drafts folder
   - Update existing drafts by ID
   - Draft metadata preserved

3. **Attachments** - Complete MIME multipart support
   - Send any file type as attachment
   - Read and extract attachments (base64 encoded)
   - Multiple attachments supported
   - Auto-detection of MIME types

4. **HTML Email** - Multipart/alternative format
   - HTML body with plain text fallback
   - Email clients display best format
   - Inline styles supported

5. **Authentication** - SMTP/IMAP with TLS encryption
   - STARTTLS for SMTP (port 587)
   - SSL/TLS for IMAP (port 993)
   - App-specific password support

### ⚠️ Limited Support

1. **OAuth** - Not implemented in standalone adapter
   - Use ArmaraOS MCP integrations for OAuth (Gmail, Outlook)
   - Standalone adapter requires username/password authentication
   - App-specific passwords recommended for Gmail

## Troubleshooting

### "adapter blocked by capability gate: email"

**Solution:** Add email to allowlist or enable IR-declared adapters:
```bash
export AINL_ALLOW_IR_DECLARED_ADAPTERS=1
```

### "email.send requires EMAIL_USERNAME and EMAIL_PASSWORD"

**Solution:** Set credentials in environment:
```bash
export EMAIL_USERNAME=your.email@gmail.com
export EMAIL_PASSWORD=your_app_password
```

### SMTP Authentication Failed

**Causes:**
1. Using regular password instead of app-specific password
2. "Less secure app access" disabled (Gmail)
3. Wrong SMTP host/port

**Solution:**
- Gmail: Use app-specific password from https://myaccount.google.com/apppasswords
- Outlook: Enable "SMTP AUTH" in account settings
- Verify SMTP host matches your provider (see table above)

### IMAP Connection Refused

**Causes:**
1. IMAP not enabled for account
2. Wrong IMAP host/port
3. Firewall blocking port 993

**Solution:**
- Gmail: Enable IMAP in Settings → Forwarding and POP/IMAP
- Check IMAP host is correct for your provider
- Ensure port 993 is open for SSL/TLS

## Further Reading

- [AINL Adapter Documentation](../docs/ADAPTERS.md)
- [ArmaraOS Email Tools](https://github.com/sbhooley/armaraos/blob/main/docs/email-adapter.md)
- [IMAP Search Reference](https://www.atmail.com/blog/imap-commands/)
- [SMTP/IMAP Provider Settings](https://www.systoolsgroup.com/imap/)

## Contributing

To improve the email adapter:

1. **Add OAuth Support** - Integrate with MCP email servers
2. **Implement Reply** - Fetch original message, set threading headers
3. **Add Attachments** - Support file attachments in send
4. **HTML Templates** - Support HTML email bodies
5. **Folder Management** - Create/delete/rename IMAP folders

See `adapters/email.py` for implementation details.
