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

            # Create fact-check prompt with strict instructions
            fact_check_prompt = f"""You are fact-checking a claim. You MUST ONLY use information from the provided search results below. DO NOT use any other knowledge or make up information.

CRITICAL RULES:
- ONLY cite information that appears in the search results below
- NEVER extrapolate or infer beyond what's explicitly stated in search results
- NEVER make up dates, positions, or events that aren't in the search results

CROSS-REFERENCE REQUIREMENT:
- To declare "True" or "False", you MUST have AT LEAST 2 DIFFERENT sources that agree
- If only 1 source mentions something, verdict is "Unverifiable" (insufficient corroboration)
- If sources contradict each other, verdict is "Conflicting Sources" or "Unverifiable"
- Count the source numbers that support each fact

CLAIM TO FACT-CHECK:
"{content}"

WEB SEARCH RESULTS:
{search_context}

Provide a structured fact-check with:
1. VERDICT: True, False, Partially True, Misleading, or Unverifiable
2. EXPLANATION: Brief explanation citing ONLY information from search results above
3. KEY EVIDENCE: Direct quotes or facts from the search results
4. SOURCES CORROBORATION: List which source numbers ([1], [2], etc.) agree on each key fact
   - Example: "Sources [1] and [3] both confirm X is Y"
   - If only 1 source, state: "Only source [2] mentions this - insufficient corroboration"

REMINDER: Without at least 2 sources agreeing, verdict CANNOT be "True" or "False"."""

            # Get LLM analysis
            headers = {
                "Authorization": f"Bearer {self.llm.api_key}",
                "Content-Type": "application/json"
            }

            # Use dedicated high-accuracy model for fact-checking
            import os
            fact_check_model = os.getenv('FACT_CHECK_MODEL', self.llm.model)

            print(f"🔍 Using fact-check model: {fact_check_model}")

            payload = {
                "model": fact_check_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a strict fact-checker. You ONLY state facts that appear in the provided search results. You NEVER make up information, dates, or events. You require AT LEAST 2 DIFFERENT sources to corroborate a fact before declaring it 'True' or 'False'. If search results don't contain the answer or only 1 source mentions it, you say 'Unverifiable'."
                    },
                    {
                        "role": "user",
                        "content": fact_check_prompt
                    }
                ],
                "max_tokens": 700,  # Increased for source cross-referencing
                "temperature": 0.1  # Lower temperature to reduce hallucination
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

            # Debug: Log what the LLM returned
            print(f"🤖 LLM FACT-CHECK RESPONSE:")
            print(f"   {analysis[:500]}...")

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
