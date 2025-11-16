# RAG (Retrieval Augmented Generation) System

The RAG system provides intelligent memory and context retrieval, allowing the bot to access relevant historical information without overwhelming the LLM's context window.

## Overview

Traditional chatbots are limited by their context window - they can only see a small number of recent messages. The RAG system solves this by implementing **hybrid memory architecture**:

- **Working Memory**: Last 10 messages from all users in the channel
- **Long-term Memory**: Semantic search across entire message history
- **User Facts**: Automatically learned preferences, projects, and skills
- **Conversation Summaries**: AI-generated summaries of past conversations

## How It Works

### 1. Automatic Embedding Generation

Every message sent in channels where the bot has access is automatically:
1. Queued for embedding generation
2. Processed every 5 minutes in batches of up to 100 messages
3. Converted to a 1536-dimensional vector using OpenAI's `text-embedding-3-small` model
4. Stored in PostgreSQL with pgvector extension

### 2. Semantic Search

When a user mentions the bot, the system:
1. Generates an embedding for the user's query
2. Performs vector similarity search using cosine distance
3. Retrieves the top 3 most semantically similar past conversations
4. Filters results by similarity threshold (default: 0.7)
5. Injects relevant context into the LLM prompt

**Example**: If you ask "how do I fix Docker networking issues?", the system finds past conversations about Docker and networking, even if they used different words.

### 3. User Fact Extraction

The system automatically learns about users by:
- Analyzing messages for factual information
- Extracting preferences (e.g., "uses Python", "prefers PostgreSQL")
- Tracking projects (e.g., "working on Discord bot")
- Noting problems (e.g., "having Docker issues")
- Recording skills (e.g., "learning RAG systems")

Facts are stored with:
- **Confidence score** (0.0 to 1.0)
- **Mention count** (how many times mentioned)
- **Source message** (where it was learned)
- **First/last confirmed** timestamps

### 4. Conversation Summarization

The system can generate concise summaries of conversation segments:
- 2-3 sentence summaries of key topics
- Focus on decisions and important information
- Stored for future reference
- Used to provide broader context without full message history

## Architecture

### Database Tables

#### `message_embeddings`
Stores vector embeddings for semantic search.
```sql
CREATE TABLE message_embeddings (
    id SERIAL PRIMARY KEY,
    message_id BIGINT REFERENCES messages(message_id),
    embedding vector(1536),  -- OpenAI text-embedding-3-small
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX ON message_embeddings
USING ivfflat (embedding vector_cosine_ops);
```

#### `conversation_summaries`
Stores AI-generated conversation summaries.
```sql
CREATE TABLE conversation_summaries (
    id SERIAL PRIMARY KEY,
    channel_id BIGINT,
    user_id BIGINT,  -- NULL for channel-wide summaries
    summary TEXT,
    message_count INTEGER,
    start_timestamp TIMESTAMP,
    end_timestamp TIMESTAMP,
    created_at TIMESTAMP
);
```

#### `user_facts`
Stores extracted facts about users.
```sql
CREATE TABLE user_facts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    fact_type VARCHAR(50),  -- 'preference', 'technical_skill', 'project', etc.
    fact TEXT,
    confidence DECIMAL(3,2) DEFAULT 0.80,
    source_message_id BIGINT,
    first_mentioned TIMESTAMP,
    last_confirmed TIMESTAMP,
    mention_count INTEGER DEFAULT 1
);
```

#### `embedding_queue`
Tracks messages pending embedding generation.
```sql
CREATE TABLE embedding_queue (
    id SERIAL PRIMARY KEY,
    message_id BIGINT REFERENCES messages(message_id),
    priority INTEGER DEFAULT 5,  -- 1 (highest) to 10 (lowest)
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP
);
```

### Background Processing

The embedding processor runs every 5 minutes:
```python
@tasks.loop(minutes=5)
async def process_embeddings():
    count = await rag.process_embedding_queue(limit=100)
    if count > 0:
        print(f"🧠 Processed {count} message embeddings")
```

Features:
- Non-blocking async processing
- Batch processing (up to 100 messages)
- Retry logic (up to 3 attempts)
- Error tracking
- Priority-based queue

### RAG Context Injection

When the bot responds, it retrieves and injects RAG context:

```python
# Get RAG context
rag_context = await rag.get_relevant_context(
    query=user_message,
    channel_id=message.channel.id,
    user_id=message.author.id,
    limit=3  # Top 3 semantic matches
)

# RAG context structure:
{
    'semantic_matches': [
        {
            'message_id': 123,
            'user_id': 456,
            'username': 'Alice',
            'content': 'message text...',
            'timestamp': datetime,
            'similarity': 0.85  # 85% similar
        }
    ],
    'user_facts': [
        {
            'fact': 'uses PostgreSQL database',
            'confidence': 0.90,
            'mention_count': 5
        }
    ],
    'recent_summary': 'Summary of recent conversation...'
}
```

This context is injected into the system prompt:
```
## RELEVANT HISTORICAL CONTEXT (RAG):

**Known Facts About User:**
- uses PostgreSQL database (confidence: 90%)
- learning RAG systems (confidence: 85%)

**Recent Conversation Summary:**
The team discussed implementing vector search for semantic similarity...

**Relevant Past Conversations:**
- [2025-01-10, 85% relevant] Alice: How do I set up pgvector in PostgreSQL?...
- [2025-01-08, 78% relevant] Bob: I'm having trouble with Docker networking...
```

## Configuration

### Environment Variables (.env)

```bash
# OpenAI API Key (required for RAG)
OPENAI_API_KEY=sk-proj-your-key-here

# RAG System Configuration
EMBEDDING_MODEL=text-embedding-3-small  # OpenAI embedding model
RAG_SIMILARITY_THRESHOLD=0.7            # Minimum similarity (0.0-1.0)
```

### Dependencies

```txt
openai==1.12.0       # OpenAI API for embeddings
httpx==0.24.1        # HTTP client (pinned for compatibility)
pgvector==0.3.5      # PostgreSQL vector extension
```

### Docker Configuration

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg15  # PostgreSQL with vector extension
    volumes:
      - ./sql/rag_migration.sql:/docker-entrypoint-initdb.d/07_rag.sql

  bot:
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      EMBEDDING_MODEL: ${EMBEDDING_MODEL}
      RAG_SIMILARITY_THRESHOLD: ${RAG_SIMILARITY_THRESHOLD}
```

## Performance

### Token Reduction
- **Before RAG**: 20 messages per user = ~4000 tokens
- **After RAG**: 10 total messages + RAG context = ~2400 tokens
- **Savings**: 40% token reduction

### Memory Access
- **Before**: Limited to last 20 messages
- **After**: Access to entire conversation history via semantic search
- **Improvement**: Unlimited historical context with compact representation

### Cost Efficiency
- **Embedding Cost**: ~$0.02 per 1M tokens (text-embedding-3-small)
- **Average Message**: ~100 tokens = $0.000002 per message
- **Batch Processing**: Amortizes API overhead
- **Overall Impact**: Negligible cost increase, significant capability improvement

### Search Performance
- **Vector Index**: IVFFlat with 100 lists for approximate nearest neighbor
- **Search Time**: ~10-50ms for similarity search
- **Database**: Connection pooling enables parallel requests
- **Throughput**: Multiple users can search simultaneously

## API Reference

### RAGSystem Class

#### `__init__(database, llm_client)`
Initialize RAG system with database and LLM client.

#### `async generate_embedding(text: str) -> Optional[List[float]]`
Generate embedding vector for a single text.

**Args:**
- `text`: Text to embed (max 8000 chars)

**Returns:**
- 1536-dimensional embedding vector or None

#### `async generate_embeddings_batch(texts: List[str]) -> List[Optional[List[float]]]`
Generate embeddings for multiple texts in batch.

**Args:**
- `texts`: List of texts to embed

**Returns:**
- List of embedding vectors (None for failed embeddings)

#### `async process_embedding_queue(limit: int = 50) -> int`
Process pending messages in embedding queue.

**Args:**
- `limit`: Maximum messages to process (default: 50)

**Returns:**
- Number of embeddings successfully generated

#### `async semantic_search(query, channel_id=None, user_id=None, limit=5, max_age_days=90) -> List[Dict]`
Search for semantically similar messages.

**Args:**
- `query`: Search query text
- `channel_id`: Limit to specific channel (optional)
- `user_id`: Limit to specific user (optional)
- `limit`: Maximum results (default: 5)
- `max_age_days`: Maximum age of messages (default: 90)

**Returns:**
- List of messages with similarity scores

#### `async get_relevant_context(query, channel_id, user_id, limit=3) -> Dict`
Get relevant context for a query using RAG.

**Args:**
- `query`: User's query/message
- `channel_id`: Channel ID
- `user_id`: User ID
- `limit`: Max semantic matches (default: 3)

**Returns:**
- Dictionary with `semantic_matches`, `user_facts`, `recent_summary`

## Monitoring

### Logs

The RAG system provides detailed logging:

```
✅ RAG system initialized (model: text-embedding-3-small)
🧠 RAG embedding processing enabled (runs every 5 minutes)
🔄 Processing 100 messages for embedding...
✅ Generated 98/100 embeddings
❌ Error generating embedding: Error code: 401...
```

### Health Checks

Monitor the embedding queue:
```sql
-- Check queue size
SELECT COUNT(*) FROM embedding_queue;

-- Check failed embeddings
SELECT * FROM embedding_queue WHERE attempts >= 3;

-- Check embedding coverage
SELECT
    COUNT(DISTINCT m.message_id) as total_messages,
    COUNT(DISTINCT me.message_id) as embedded_messages,
    ROUND(100.0 * COUNT(DISTINCT me.message_id) / COUNT(DISTINCT m.message_id), 2) as coverage_percent
FROM messages m
LEFT JOIN message_embeddings me ON m.message_id = me.message_id;
```

## Troubleshooting

### RAG System Disabled

**Symptom**: `⚠️ Warning: OPENAI_API_KEY not set - RAG system will be disabled`

**Solution**: Add valid OpenAI API key to `.env`:
```bash
OPENAI_API_KEY=sk-proj-your-key-here
```

### 401 Authentication Error

**Symptom**: `Error code: 401 - Incorrect API key provided`

**Solutions**:
1. Verify API key at https://platform.openai.com/api-keys
2. Ensure key is a project-based key (`sk-proj-...`)
3. Check for trailing whitespace in `.env` file
4. Rebuild container: `docker-compose up -d --build bot`

### Embedding Queue Growing

**Symptom**: Queue size keeps increasing

**Possible Causes**:
1. OpenAI API rate limits
2. Invalid API key
3. Network issues

**Solution**: Check logs for errors and verify API key

### Low Similarity Scores

**Symptom**: Semantic search not returning relevant results

**Solutions**:
1. Lower similarity threshold in `.env`: `RAG_SIMILARITY_THRESHOLD=0.6`
2. Increase result limit in code
3. Check if embeddings are being generated

## Future Enhancements

Potential improvements to the RAG system:

1. **Advanced Fact Extraction**
   - Entity recognition for better fact categorization
   - Confidence decay over time
   - Contradiction detection for fact updates

2. **Smarter Summarization**
   - Hierarchical summaries (day → week → month)
   - Topic-based clustering
   - Automatic summary triggers

3. **Enhanced Search**
   - Hybrid search (semantic + keyword)
   - Time-weighted relevance
   - User-specific relevance tuning

4. **Performance Optimization**
   - Embedding caching
   - Incremental index updates
   - Query result caching

5. **Analytics**
   - Embedding quality metrics
   - Search effectiveness tracking
   - User engagement with recalled context

## Credits

RAG system implementation by Claude Code in collaboration with the bot maintainer.

- **Vector Database**: PostgreSQL with pgvector extension
- **Embeddings**: OpenAI text-embedding-3-small
- **Architecture**: Hybrid memory with working + long-term storage
- **Search Algorithm**: Cosine similarity with IVFFlat indexing
