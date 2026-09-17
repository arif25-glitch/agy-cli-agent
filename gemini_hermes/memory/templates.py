DEFAULT_MEMORY_TEMPLATE = """# Gemini-Hermes Long-Term Memory

## System & Agent Directives
- Role: Gemini-Hermes Autonomous Assistant & Colleague
- Engine: Antigravity CLI (agy) Proxy Engine
- Gateway: Telegram Bot
- Persistence: Continuous memory across restarts and sessions

## Key Facts & Lessons
- Initialized: {timestamp}
"""

DEFAULT_USER_TEMPLATE = """# User Profile & Preferences

## User Information
- Primary Interface: Telegram Messenger
- Preferred Response Style: Clear, structured, agentic, direct, using code blocks when relevant

## User Specific Preferences & Context
- (Learned preferences will be recorded here automatically)
"""
