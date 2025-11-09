"""
Self-knowledge system for WompBot to answer questions about itself
"""
import os
import re

class SelfKnowledge:
    def __init__(self):
        self.docs_path = os.path.join(os.path.dirname(__file__), '..', 'docs')
        self.readme_path = os.path.join(os.path.dirname(__file__), '..', 'README.md')

    def is_about_self(self, message_content):
        """Detect if user is asking about WompBot itself"""
        content_lower = message_content.lower()

        # Self-referential patterns
        self_patterns = [
            r'\b(how do (i|you)|can (i|you)|what (can|does|is)|tell me about)\b.*\b(wompbot|you|this bot|the bot)\b',
            r'\bwompbot\b.*\b(do|work|feature|command|can)\b',
            r'\b(what are|show me|list)\b.*\b(your|wompbot\'?s?)\b.*\b(feature|command|capabilit)',
            r'\b(how (to|do i))\b.*\b(use|trigger|activate|enable|set up)\b',
            r'\b(what|which|show)\b.*\bcommand',
            r'\b(explain|describe|tell me about)\b.*\b(claim|fact.?check|quote|wrapped|search|rate limit)',
            r'\bhelp\b.*\bwith\b',
            r'\bwhat (is|does)\b.*\b(your|this)\b',
        ]

        for pattern in self_patterns:
            if re.search(pattern, content_lower):
                return True

        # Direct feature questions
        features = [
            'claim', 'fact-check', 'fact check', 'quote', 'wrapped', 'search',
            'rate limit', 'leaderboard', 'iracing', 'event', 'reminder',
            'hot take', 'contradiction', 'gdpr', 'privacy', 'data deletion'
        ]

        for feature in features:
            if feature in content_lower and any(word in content_lower for word in ['how', 'what', 'explain', 'tell', 'show']):
                return True

        return False

    def get_relevant_docs(self, message_content):
        """Load relevant documentation based on question"""
        content_lower = message_content.lower()
        docs_to_load = []

        # Always include README for general questions
        docs_to_load.append(self.readme_path)

        # Feature-specific docs
        if any(word in content_lower for word in ['claim', 'track', 'contradiction']):
            docs_to_load.append(os.path.join(self.docs_path, 'features', 'CLAIMS.md'))

        if any(word in content_lower for word in ['fact', 'check', 'verify', '⚠️']):
            docs_to_load.append(os.path.join(self.docs_path, 'features', 'FACT_CHECKING.md'))

        if any(word in content_lower for word in ['quote', 'save', '☁️', 'cloud']):
            docs_to_load.append(os.path.join(self.docs_path, 'features', 'QUOTES.md'))

        if any(word in content_lower for word in ['wrapped', 'stats', 'year']):
            docs_to_load.append(os.path.join(self.docs_path, 'features', 'WRAPPED.md'))

        if any(word in content_lower for word in ['event', 'schedule', 'reminder']):
            docs_to_load.append(os.path.join(self.docs_path, 'features', 'EVENTS.md'))

        if any(word in content_lower for word in ['cost', 'rate limit', 'spending', 'abuse', 'token']):
            docs_to_load.append(os.path.join(self.docs_path, 'COST_OPTIMIZATION.md'))

        if any(word in content_lower for word in ['config', 'setup', 'install', 'environment', '.env']):
            docs_to_load.append(os.path.join(self.docs_path, 'CONFIGURATION.md'))

        if any(word in content_lower for word in ['iracing', 'irating', 'race', 'racing']):
            docs_to_load.append(os.path.join(self.docs_path, 'features', 'IRACING.md'))

        if any(word in content_lower for word in ['privacy', 'gdpr', 'data', 'delete', 'opt out']):
            docs_to_load.append(os.path.join(self.docs_path, 'guides', 'GDPR_COMPLIANCE.md'))

        return docs_to_load

    def load_documentation(self, message_content):
        """Load and format relevant documentation for LLM context"""
        if not self.is_about_self(message_content):
            return None

        docs = self.get_relevant_docs(message_content)

        doc_content = []
        for doc_path in docs:
            if os.path.exists(doc_path):
                try:
                    with open(doc_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Limit each doc to 3000 chars to avoid context bloat
                        if len(content) > 3000:
                            content = content[:3000] + "\n\n[... truncated for brevity ...]"

                        doc_name = os.path.basename(doc_path)
                        doc_content.append(f"=== {doc_name} ===\n{content}\n")
                except Exception as e:
                    print(f"⚠️  Error loading {doc_path}: {e}")

        if not doc_content:
            return None

        return "\n".join(doc_content)

    def format_for_llm(self, message_content):
        """Format documentation as LLM context"""
        docs = self.load_documentation(message_content)

        if not docs:
            return None

        return f"""[WOMPBOT KNOWLEDGE BASE - Use this to answer questions about WompBot's features]

{docs}

[END KNOWLEDGE BASE - Answer the user's question based on the documentation above. Be conversational and helpful. Don't just regurgitate docs - explain things naturally.]"""
