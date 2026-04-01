"""migrate HTTP/Email/Code/Script skills to Toolkit format

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-02-14

Converts existing skills of old types (http, email, code, script) into
toolkit type by generating a Toolkit Python wrapper and storing it in
toolkit_content. The original config is preserved in toolkit_meta for
reference.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import json


# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(conn, table_name: str) -> bool:
    return sa.inspect(conn).has_table(table_name)


def _generate_http_toolkit(name: str, description: str, config: dict) -> str:
    """Generate Toolkit wrapper for HTTP skill."""
    url = config.get("url", "")
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})
    headers_str = json.dumps(headers, ensure_ascii=False) if headers else "{}"

    return f'''"""
title: {name}
description: {description}
version: 1.0.0
author: auto-migrated
"""

import httpx
from pydantic import BaseModel, Field


class Valves(BaseModel):
    url: str = Field("{url}", description="Request URL")
    method: str = Field("{method}", description="HTTP method")
    timeout: int = Field(30, description="Timeout seconds")


class Tools:
    def __init__(self):
        self.valves = Valves()

    async def call_api(self, params: str = "") -> str:
        """Call the HTTP API
        :param params: Optional query parameters or request body
        """
        headers = {headers_str}
        async with httpx.AsyncClient(
            timeout=self.valves.timeout, verify=False
        ) as client:
            if self.valves.method in ("GET", "HEAD"):
                resp = await client.request(
                    self.valves.method, self.valves.url,
                    headers=headers, params={{"q": params}} if params else None,
                )
            else:
                resp = await client.request(
                    self.valves.method, self.valves.url,
                    headers=headers, json={{"data": params}} if params else None,
                )
            return resp.text[:5000]
'''


def _generate_email_toolkit(name: str, description: str, config: dict) -> str:
    """Generate Toolkit wrapper for Email skill."""
    smtp_host = config.get("smtp_host", "")
    smtp_port = config.get("smtp_port", 587)
    from_email = config.get("from_email", "")

    return f'''"""
title: {name}
description: {description}
version: 1.0.0
author: auto-migrated
"""

from pydantic import BaseModel, Field


class Valves(BaseModel):
    smtp_host: str = Field("{smtp_host}", description="SMTP host")
    smtp_port: int = Field({smtp_port}, description="SMTP port")
    from_email: str = Field("{from_email}", description="Sender email")


class Tools:
    def __init__(self):
        self.valves = Valves()

    async def send_email(self, to: str, subject: str, body: str) -> str:
        """Send an email
        :param to: Recipient email address
        :param subject: Email subject
        :param body: Email body content
        """
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.valves.from_email
        msg["To"] = to

        with smtplib.SMTP(self.valves.smtp_host, self.valves.smtp_port) as server:
            server.starttls()
            server.send_message(msg)

        return f"Email sent to {{to}}"
'''


def _generate_code_toolkit(name: str, description: str, config: dict) -> str:
    """Generate Toolkit wrapper for Code skill."""
    template = config.get("code_template", "") or config.get("template", "")
    language = config.get("language", "python")

    # Escape triple quotes in template
    safe_template = template.replace('"""', '\\"\\"\\"') if template else ""

    return f'''"""
title: {name}
description: {description}
version: 1.0.0
author: auto-migrated
"""


class Tools:
    async def execute_code(self, code: str = "") -> str:
        """Execute code
        :param code: Code to execute (default uses template)
        """
        source = code or """{safe_template}"""
        if not source:
            return "No code provided"

        import io
        import contextlib

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(source, {{"__builtins__": __builtins__}})
        return output.getvalue() or "(no output)"
'''


def _generate_script_toolkit(
    name: str, description: str,
    script_content: str, script_language: str,
) -> str:
    """Generate Toolkit wrapper for Script skill (single script)."""
    # Escape triple quotes
    safe_content = script_content.replace('"""', '\\"\\"\\"') if script_content else ""

    return f'''"""
title: {name}
description: {description}
version: 1.0.0
author: auto-migrated
"""


class Tools:
    async def run_script(self, input_data: str = "") -> str:
        """Run the script
        :param input_data: Optional input data for the script
        """
        import io
        import contextlib

        source = """{safe_content}"""
        if not source:
            return "No script content"

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(source, {{"__builtins__": __builtins__, "input_data": input_data}})
        return output.getvalue() or "(no output)"
'''


def upgrade() -> None:
    conn = op.get_bind()
    has_skill_scripts = _has_table(conn, "skill_scripts")

    # 1. Migrate HTTP skills
    rows = conn.execute(text(
        "SELECT id, name, description, config FROM skills "
        "WHERE type = 'http' AND is_deleted = false"
    )).fetchall()
    for row in rows:
        config = json.loads(row[3]) if row[3] else {}
        toolkit_content = _generate_http_toolkit(
            row[1] or "HTTP Tool", row[2] or "", config,
        )
        toolkit_meta = {
            "migrated_from": "http",
            "original_config": config,
        }
        conn.execute(text(
            "UPDATE skills SET type = 'toolkit', "
            "toolkit_content = :content, toolkit_meta = :meta "
            "WHERE id = :id"
        ), {"content": toolkit_content, "meta": json.dumps(toolkit_meta), "id": row[0]})

    # 2. Migrate Email skills
    rows = conn.execute(text(
        "SELECT id, name, description, config FROM skills "
        "WHERE type = 'email' AND is_deleted = false"
    )).fetchall()
    for row in rows:
        config = json.loads(row[3]) if row[3] else {}
        toolkit_content = _generate_email_toolkit(
            row[1] or "Email Tool", row[2] or "", config,
        )
        toolkit_meta = {
            "migrated_from": "email",
            "original_config": config,
        }
        conn.execute(text(
            "UPDATE skills SET type = 'toolkit', "
            "toolkit_content = :content, toolkit_meta = :meta "
            "WHERE id = :id"
        ), {"content": toolkit_content, "meta": json.dumps(toolkit_meta), "id": row[0]})

    # 3. Migrate Code skills
    rows = conn.execute(text(
        "SELECT id, name, description, config FROM skills "
        "WHERE type = 'code' AND is_deleted = false"
    )).fetchall()
    for row in rows:
        config = json.loads(row[3]) if row[3] else {}
        toolkit_content = _generate_code_toolkit(
            row[1] or "Code Tool", row[2] or "", config,
        )
        toolkit_meta = {
            "migrated_from": "code",
            "original_config": config,
        }
        conn.execute(text(
            "UPDATE skills SET type = 'toolkit', "
            "toolkit_content = :content, toolkit_meta = :meta "
            "WHERE id = :id"
        ), {"content": toolkit_content, "meta": json.dumps(toolkit_meta), "id": row[0]})

    # 4. Migrate Script skills (from skill.script_content)
    rows = conn.execute(text(
        "SELECT id, name, description, script_content, script_language FROM skills "
        "WHERE type = 'script' AND is_deleted = false"
    )).fetchall()
    for row in rows:
        script_content = row[3] or ""
        script_language = row[4] or "python"

        # skill_scripts is optional in some historical DB states.
        script_rows = []
        if has_skill_scripts:
            script_rows = conn.execute(text(
                "SELECT filename, content, language, is_entry "
                "FROM skill_scripts WHERE skill_id = :sid "
                "ORDER BY sort_order"
            ), {"sid": row[0]}).fetchall()

        if script_rows:
            # Use entry script content
            entry_content = ""
            for sr in script_rows:
                if sr[3]:  # is_entry
                    entry_content = sr[1]
                    script_language = sr[2]
                    break
            if not entry_content and script_rows:
                entry_content = script_rows[0][1]
            script_content = entry_content or script_content

        toolkit_content = _generate_script_toolkit(
            row[1] or "Script Tool", row[2] or "",
            script_content, script_language,
        )
        toolkit_meta = {
            "migrated_from": "script",
            "original_script_language": script_language,
            "had_multi_scripts": bool(script_rows),
        }
        conn.execute(text(
            "UPDATE skills SET type = 'toolkit', "
            "toolkit_content = :content, toolkit_meta = :meta "
            "WHERE id = :id"
        ), {"content": toolkit_content, "meta": json.dumps(toolkit_meta), "id": row[0]})


def downgrade() -> None:
    conn = op.get_bind()

    # Restore original types from toolkit_meta
    rows = conn.execute(text(
        "SELECT id, toolkit_meta FROM skills "
        "WHERE type = 'toolkit' AND toolkit_meta IS NOT NULL"
    )).fetchall()
    for row in rows:
        meta = json.loads(row[1]) if row[1] else {}
        original_type = meta.get("migrated_from")
        if original_type:
            conn.execute(text(
                "UPDATE skills SET type = :orig_type WHERE id = :id"
            ), {"orig_type": original_type, "id": row[0]})
