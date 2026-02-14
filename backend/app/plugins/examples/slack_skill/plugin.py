"""
Slack Notification Skill Plugin

Demonstrates how to build a SkillPlugin for NovusAI.

Key concepts shown:
  - SkillPlugin interface (get_skill_type, get_skill_config_schema, resolve, execute)
  - Skill configuration (webhook_url, default_channel, bot_name)
  - Tool definitions for LLM function calling
  - Tool execution with HTTP webhook call

Skill Type: slack
Tools provided:
  - send_slack_message: Send a message to a Slack channel via webhook

To install for development:
  POST /admin/plugins/install
  { "entry_point": "app.plugins.examples.slack_skill.plugin.NovusaiSlackSkillPlugin" }
"""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.plugins.context import PluginContext
from app.plugins.extensions.skill_plugin import SkillPlugin


class NovusaiSlackSkillPlugin(SkillPlugin):
    """
    Slack Notification Skill Plugin

    Allows AI agents to send messages to Slack channels.
    When a user creates a "slack" type Skill, they configure
    webhook_url and default_channel. The agent can then call
    send_slack_message to post to Slack.
    """

    # ========================================
    # Required metadata
    # ========================================

    @property
    def name(self) -> str:
        return "novusai-slack-skill"

    @property
    def display_name(self) -> str:
        return "Slack Notification"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ========================================
    # Optional metadata
    # ========================================

    @property
    def description(self) -> str:
        return (
            "Send messages to Slack channels via webhook. "
            "Provides a 'slack' Skill type for AI agents."
        )

    @property
    def author(self) -> str:
        return "NovusAI Team"

    @property
    def icon(self) -> str:
        return "lucide:message-square"

    @property
    def required_permissions(self) -> list[str]:
        """Needs outbound HTTP to call Slack webhook."""
        return ["http:outbound"]

    # ========================================
    # SkillPlugin interface
    # ========================================

    def get_skill_type(self) -> str:
        """
        Unique Skill type identifier.

        When users create a new Skill in the admin/tenant panel,
        they can select "slack" as the Skill type.
        """
        return "slack"

    def get_skill_display_name(self) -> str:
        """Display name shown in the Skill type selector."""
        return "Slack 通知"

    def get_skill_icon(self) -> str:
        """Icon for this Skill type in the UI."""
        return "lucide:message-square"

    def get_skill_config_schema(self) -> dict[str, Any]:
        """
        JSON Schema for Skill-level configuration.

        When a user creates a "slack" Skill, the frontend renders
        this schema as a dynamic form via the SchemaForm component.

        Each Skill instance gets its own config (e.g. different
        webhook URLs for different Slack workspaces).
        """
        return {
            "type": "object",
            "properties": {
                "webhook_url": {
                    "type": "string",
                    "title": "Webhook URL",
                    "description": (
                        "Slack Incoming Webhook URL "
                        "(e.g. https://hooks.slack.com/services/...)"
                    ),
                    "format": "password",
                },
                "default_channel": {
                    "type": "string",
                    "title": "Default Channel",
                    "description": "Default channel to post messages (e.g. #general)",
                },
                "bot_name": {
                    "type": "string",
                    "title": "Bot Name",
                    "description": "Display name for the bot in Slack",
                    "default": "NovusAI Bot",
                },
                "bot_icon": {
                    "type": "string",
                    "title": "Bot Icon Emoji",
                    "description": "Emoji icon for the bot (e.g. :robot_face:)",
                    "default": ":robot_face:",
                },
            },
            "required": ["webhook_url"],
        }

    def resolve(
        self,
        skill_config: dict[str, Any],
    ) -> list[ToolDefinition]:
        """
        Resolve a Skill instance into ToolDefinitions for the LLM.

        Called by SkillResolver when an agent with a "slack" Skill
        starts a conversation. The returned ToolDefinitions are added
        to the LLM's available tools.

        Args:
            skill_config: The specific Skill's config (webhook_url, etc.)

        Returns:
            List of ToolDefinitions the LLM can call.
        """
        return [
            ToolDefinition(
                name="send_slack_message",
                description=(
                    "Send a message to a Slack channel. "
                    "Use this to notify team members or post updates."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Message text to send (supports Slack markdown)",
                        },
                        "channel": {
                            "type": "string",
                            "description": (
                                "Target channel (e.g. #general). "
                                "If not specified, uses the default channel."
                            ),
                        },
                    },
                    "required": ["text"],
                },
            ),
        ]

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: Any,
    ) -> Any:
        """
        Execute a tool call from the LLM.

        Called by Sandbox when the LLM calls send_slack_message.
        The context contains the Skill config with webhook_url, etc.

        Args:
            tool_name: "send_slack_message"
            arguments: {"text": "...", "channel": "#..."}
            context: Execution context with skill config

        Returns:
            Result dict sent back to the LLM.
        """
        if tool_name == "send_slack_message":
            return await self._send_message(arguments, context)

        return {"error": f"Unknown tool: {tool_name}"}

    async def _send_message(
        self,
        arguments: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Send a message to Slack via Incoming Webhook.

        In production, this makes an HTTP POST to the webhook URL.
        For the example, we return a mock success response.

        Real implementation would use httpx or aiohttp:

            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()
        """
        text = arguments.get("text", "")
        channel = arguments.get("channel")

        skill_cfg = context.skill_config
        default_channel = skill_cfg.get("default_channel", "#general")
        bot_name = skill_cfg.get("bot_name", "NovusAI Bot")

        target_channel = channel or default_channel

        # Mock: construct the payload that would be sent
        payload = {
            "channel": target_channel,
            "username": bot_name,
            "text": text,
            "icon_emoji": ":robot_face:",
        }

        # Mock success response
        return {
            "success": True,
            "channel": target_channel,
            "message_preview": text[:100],
            "payload": payload,
            "note": "This is a mock response. Configure webhook_url for real Slack delivery.",
        }

    # ========================================
    # Lifecycle hooks
    # ========================================

    async def on_enable(self, ctx: PluginContext) -> None:
        """Called when the plugin is enabled."""
        if ctx.logger:
            ctx.logger.info("Slack Skill plugin enabled — skill type 'slack' registered")

    async def on_disable(self, ctx: PluginContext) -> None:
        """Called when the plugin is disabled."""
        if ctx.logger:
            ctx.logger.info("Slack Skill plugin disabled — skill type 'slack' unregistered")
