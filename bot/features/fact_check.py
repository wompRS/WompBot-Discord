"""
Fact-Check Feature
React with ⚠️ emoji to trigger a fact-check on a message
"""

class FactChecker:
    def __init__(self, db, llm, search):
        self.db = db
        self.llm = llm
        self.search = search

    async def fact_check_message(self, message, reactor_user):
        """
        Fact-check a message using web search and LLM analysis

        Args:
            message: Discord message to fact-check
            reactor_user: User who requested the fact-check

        Returns:
            dict: Fact-check results with verdict and sources
        """
        try:
            content = message.content

            if not content or len(content) < 10:
                return {
                    'success': False,
                    'error': 'Message too short to fact-check'
                }

            # Search for information about the claim
            search_results = self.search.search(content)

            if not search_results:
                return {
                    'success': False,
                    'error': 'No search results found'
                }

            # Format search results for LLM
            search_context = self.search.format_results_for_llm(search_results)

            # Create fact-check prompt
            fact_check_prompt = f"""Analyze the following claim and determine its factual accuracy based on the search results provided.

CLAIM TO FACT-CHECK:
"{content}"

WEB SEARCH RESULTS:
{search_context}

Provide a structured fact-check with:
1. VERDICT: True, False, Partially True, Misleading, or Unverifiable
2. EXPLANATION: Brief explanation (2-3 sentences max)
3. KEY EVIDENCE: Most relevant evidence from search results
4. SOURCES: Reference which sources support your verdict

Be direct and factual. Don't hedge unnecessarily."""

            # Get LLM analysis
            headers = {
                "Authorization": f"Bearer {self.llm.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.llm.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert fact-checker. Analyze claims objectively based on evidence. Be concise and direct."
                    },
                    {
                        "role": "user",
                        "content": fact_check_prompt
                    }
                ],
                "max_tokens": 600,
                "temperature": 0.3
            }

            import requests
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            analysis = response.json()['choices'][0]['message']['content']

            # Store fact-check in database
            self.db.store_fact_check(
                message_id=message.id,
                user_id=message.author.id,
                username=str(message.author),
                channel_id=message.channel.id,
                claim_text=content,
                fact_check_result=analysis,
                search_results=search_results[:3],  # Store top 3 sources
                requested_by_user_id=reactor_user.id,
                requested_by_username=str(reactor_user)
            )

            return {
                'success': True,
                'analysis': analysis,
                'sources': search_results[:3]
            }

        except Exception as e:
            print(f"❌ Error fact-checking message: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def parse_verdict(self, analysis_text):
        """Extract verdict emoji from analysis"""
        verdict_lower = analysis_text.lower()

        if 'verdict: true' in verdict_lower or 'verdict: accurate' in verdict_lower:
            return '✅'
        elif 'verdict: false' in verdict_lower or 'verdict: incorrect' in verdict_lower:
            return '❌'
        elif 'verdict: partially true' in verdict_lower or 'verdict: mixed' in verdict_lower:
            return '🔀'
        elif 'verdict: misleading' in verdict_lower:
            return '⚠️'
        else:
            return '❓'
