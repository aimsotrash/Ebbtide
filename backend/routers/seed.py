"""Seed endpoint — inserts synthetic demo chunks with varied retention profiles + pre-assigned categories."""
import random
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from database.db import get_all_chunks, insert_chunk, update_chunk_category
from routers.deps import get_current_user_id
from intelligence.embeddings import embed_texts
from intelligence.retrieval import add_chunks

router = APIRouter()

# Each tuple: (content, source_file, profile, category)
# Profiles: strong / fading / weak / critical → drives retention via backdated last_accessed.
# Category is pre-assigned (no LLM call needed) so the Knowledge Forest splits cleanly.
_SEED_ITEMS = [
    # ─────────── DEVELOPMENT (strong) ───────────
    ("Binary search divides the search space in half each step. Check the midpoint; if the target is smaller go left, larger go right. Time complexity O(log n), space O(1). Works only on sorted arrays.", "demo/algorithms.md", "strong", "Computer Science"),
    ("Quick sort picks a pivot, partitions the array around it, then recursively sorts both halves. Average O(n log n), worst case O(n²). In-place but not stable.", "demo/algorithms.md", "strong", "Computer Science"),
    ("Dynamic programming stores solutions to overlapping subproblems to avoid recomputation. Top-down (memoization) or bottom-up (tabulation). Key property: optimal substructure.", "demo/algorithms.md", "strong", "Computer Science"),
    ("Hash tables map keys to indices via a hash function. Collision handling: chaining or open addressing. Average O(1) for insert/lookup/delete.", "demo/algorithms.md", "strong", "Computer Science"),
    ("BFS uses a queue to explore nodes level by level — ideal for shortest path in unweighted graphs. DFS uses a stack to go deep first — useful for cycle detection.", "demo/algorithms.md", "strong", "Computer Science"),
    ("Merge sort splits arrays in half, sorts each half recursively, then merges. Always O(n log n) time. Stable and predictable but requires O(n) extra space.", "demo/algorithms.md", "strong", "Computer Science"),
    ("Git rebase rewrites commit history by replaying commits on top of another base. Cleaner than merge but never rebase shared/pushed branches.", "demo/git.md", "strong", "Computer Science"),
    ("Python list comprehensions: [expr for x in iterable if cond]. Faster than a for-loop with append. Avoid for side effects — use a regular loop.", "demo/python.md", "strong", "Computer Science"),
    ("React hooks must be called at the top level of a function component. Never inside loops, conditions, or nested functions. Order must be stable across renders.", "demo/react.md", "strong", "Computer Science"),
    ("TypeScript discriminated unions: tag each variant with a literal type. Switch on the tag and TS narrows automatically — exhaustive checks via 'never'.", "demo/typescript.md", "strong", "Computer Science"),
    ("Tries store strings character-by-character. Each node represents a prefix. O(m) insert/search where m is string length. Used in autocomplete.", "demo/algorithms.md", "strong", "Computer Science"),

    # ─────────── AI / ML (fading) ───────────
    ("Gradient descent moves parameters in the direction of steepest loss decrease. Learning rate controls step size — too large oscillates, too small converges slowly.", "demo/ml.md", "fading", "AI/ML"),
    ("Overfitting: model memorises training noise and fails on new data. Fixes: dropout, L2 regularisation, data augmentation, early stopping.", "demo/ml.md", "fading", "AI/ML"),
    ("Attention computes a weighted sum of values using scaled dot-product (Q·Kᵀ/√d, softmax). Self-attention lets every token attend to every other — the transformer backbone.", "demo/ml.md", "fading", "AI/ML"),
    ("Convolutional layers detect local spatial features via learned filters. Pooling layers downsample. Parameter sharing drastically reduces complexity vs dense layers.", "demo/ml.md", "fading", "AI/ML"),
    ("Batch normalisation normalises activations across the batch dimension. Allows higher learning rates and reduces internal covariate shift. Train/eval modes differ.", "demo/ml.md", "fading", "AI/ML"),
    ("Cross-entropy loss: -Σ y_i log(p_i). Used for classification when outputs are probabilities. Pairs with softmax in the final layer.", "demo/ml.md", "fading", "AI/ML"),
    ("Word embeddings map tokens to dense vectors where similar meanings cluster. Word2Vec, GloVe were early; today contextual embeddings (BERT, GPT) dominate.", "demo/ml.md", "fading", "AI/ML"),
    ("Reinforcement learning loop: agent observes state, picks action, environment returns reward + next state. Policy maximises expected discounted return.", "demo/ml.md", "fading", "AI/ML"),
    ("Vector embeddings encode semantic meaning as high-dimensional points. Cosine similarity ≈ angle between vectors. ChromaDB and Pinecone are popular vector stores.", "demo/ml.md", "fading", "AI/ML"),
    ("RAG (retrieval-augmented generation): retrieve relevant chunks from a vector DB, stuff them into the LLM context, then generate. Beats fine-tuning for fact-recall use cases.", "demo/ml.md", "fading", "AI/ML"),
    ("LoRA fine-tuning trains low-rank update matrices instead of all model weights. ~10000x fewer trainable params, comparable quality, runs on consumer GPUs.", "demo/ml.md", "fading", "AI/ML"),

    # ─────────── SYSTEM DESIGN (mixed) ───────────
    ("TCP three-way handshake: SYN → SYN-ACK → ACK. Establishes sequence numbers for reliable ordered delivery. Teardown uses FIN/FIN-ACK/ACK.", "demo/system_design.md", "strong", "System Design"),
    ("TLS handshake: client hello → server hello + cert → key exchange (ECDHE) → finished. Result: symmetric session keys with forward secrecy.", "demo/system_design.md", "strong", "System Design"),
    ("HTTP/2 adds multiplexing (multiple streams per connection), header compression (HPACK), server push, binary framing. HTTP/3 uses QUIC over UDP.", "demo/system_design.md", "fading", "System Design"),
    ("Load balancing strategies: round robin, least connections, IP hash. Layer 4 routes by IP/port; Layer 7 can route by HTTP path/header.", "demo/system_design.md", "fading", "System Design"),
    ("Caching layers: CPU L1/L2 (ns), Redis (µs), CDN edge (ms). Invalidation: TTL, write-through, write-back, cache-aside.", "demo/system_design.md", "fading", "System Design"),
    ("CAP theorem: distributed systems can guarantee at most two of Consistency, Availability, Partition tolerance. Partitions are inevitable, so pick CP or AP.", "demo/system_design.md", "weak", "System Design"),
    ("Database normalisation: 1NF atomic values, 2NF no partial deps, 3NF no transitive deps, BCNF every determinant is a candidate key.", "demo/system_design.md", "weak", "System Design"),
    ("ACID: Atomicity, Consistency, Isolation, Durability. Foundation of relational databases. BASE (eventual consistency) is the NoSQL counterpart.", "demo/system_design.md", "weak", "System Design"),
    ("B+ tree indexes store sorted data in a balanced tree, records only in leaves. Self-balancing, O(log n) depth — used by virtually every relational DB.", "demo/system_design.md", "weak", "System Design"),
    ("Eventual consistency: replicas converge after writes propagate. Strong consistency requires consensus (Raft/Paxos). Tunable in Cassandra, DynamoDB.", "demo/system_design.md", "weak", "System Design"),
    ("Microservices vs monolith: microservices give independent deploys and team autonomy but pay network + ops complexity. Start monolith, split when boundaries are real.", "demo/system_design.md", "critical", "System Design"),
    ("Kafka topics are partitioned, ordered logs. Consumers track offsets; producers append. Retention by time or size. Decouples producers from consumers.", "demo/system_design.md", "critical", "System Design"),

    # ─────────── PRODUCTIVITY (mostly strong/fading) ───────────
    ("Deep work: 90-120 minute blocks of distraction-free focus on a single cognitively demanding task. Schedule, don't react. Phones in another room.", "demo/productivity.md", "strong", "Productivity"),
    ("GTD capture rule: get every commitment out of your head into a trusted system within 2 minutes of it appearing. Inbox → process → next-action.", "demo/productivity.md", "strong", "Productivity"),
    ("Pomodoro: 25min focused work, 5min break, repeat. After 4 cycles take a longer 15-30min break. The timer is a commitment device, not a productivity hack.", "demo/productivity.md", "strong", "Productivity"),
    ("Time blocking beats todo lists for high-leverage work. Pre-allocate your day so reactive tasks can't displace strategic ones. Defend the blocks ruthlessly.", "demo/productivity.md", "fading", "Productivity"),
    ("Eisenhower matrix: urgent/important quadrants. Most 'urgent' is not important. Schedule important-not-urgent (Q2) — that's where leverage lives.", "demo/productivity.md", "fading", "Productivity"),
    ("Spaced repetition uses increasing intervals between reviews — exploits the testing effect. Anki and SuperMemo schedule reviews algorithmically.", "demo/productivity.md", "fading", "Productivity"),
    ("The two-minute rule: if a task takes less than 2 minutes, do it now. Anything longer goes on the calendar or task list.", "demo/productivity.md", "weak", "Productivity"),
    ("Single-tasking outperforms multitasking on cognitively demanding work — context switching imposes a 20-40% efficiency tax. Batch similar tasks.", "demo/productivity.md", "weak", "Productivity"),
    ("Inbox zero is a workflow, not a metric. Process by deciding: delete, delegate, defer, do. Email is someone else's todo list, opened on your time.", "demo/productivity.md", "weak", "Productivity"),
    ("Weekly review: 30 minutes every Friday. Process inboxes, review goals, plan next week. Without it GTD collapses into chaos.", "demo/productivity.md", "critical", "Productivity"),
    ("Default to writing things down. Memory is unreliable; an external system is leverage. Bullet journals, Notion, plain markdown — pick one and commit.", "demo/productivity.md", "critical", "Productivity"),

    # ─────────── PERSONAL (mostly weak/critical — these are the most forgotten) ───────────
    ("Mom's birthday: October 14. She loves dark chocolate, hates flowers. Call the morning of, dinner reservation Saturday after.", "demo/personal.md", "strong", "Personal"),
    ("Apartment lease renews June 2026 — start looking March if not staying. Current rent $1850, gym + utilities included.", "demo/personal.md", "fading", "Personal"),
    ("Dentist appointment every 6 months — last visit March 12. Insurance covers 2 cleanings per year. Dr. Chen, downtown clinic.", "demo/personal.md", "fading", "Personal"),
    ("Workout split (4 days): push, pull, legs, accessory. Squat 1RM 285lb, deadlift 315lb, bench 195lb as of last test.", "demo/personal.md", "weak", "Personal"),
    ("Books to read this year: Designing Data-Intensive Applications, Crime and Punishment, The Pragmatic Programmer, Atomic Habits, Sapiens.", "demo/personal.md", "weak", "Personal"),
    ("Coffee at home: 15g beans, 250g water, 30s bloom, 2:30 total brew. V60 dripper, medium-fine grind, water just off boil.", "demo/personal.md", "weak", "Personal"),
    ("Passport expires August 2027. Renewal takes 4-6 weeks routine, 2-3 expedited ($60 extra). Need new passport photo first.", "demo/personal.md", "critical", "Personal"),
    ("Emergency fund target: 6 months of expenses ≈ $18000. Current: $11200. Auto-transfer $400/month from checking.", "demo/personal.md", "critical", "Personal"),
    ("Wifi password: change every 6 months. Router admin login is on the back. Mesh network — primary in living room, satellite in bedroom.", "demo/personal.md", "critical", "Personal"),
    ("Driver's license renewal: every 5 years, online if no address change. Last renewed July 2023 — next due 2028.", "demo/personal.md", "critical", "Personal"),
]

# Profile → (min_days, max_days, min_access, max_access) for backdated last_accessed.
_PROFILES = {
    "strong":   (1,   4,   4, 8),
    "fading":   (14,  25,  2, 3),
    "weak":     (45,  70,  1, 2),
    "critical": (100, 160, 0, 1),
}


@router.post("/seed")
def seed_demo_data(user_id: str = Depends(get_current_user_id)):
    existing = get_all_chunks(user_id)
    already = sum(1 for r in existing if (r["source_file"] or "").startswith("demo/"))
    if already >= 10:
        return {"message": f"Demo data already loaded ({already} demo chunks present).", "seeded": 0}

    now = datetime.now(tz=timezone.utc)
    texts = [item[0] for item in _SEED_ITEMS]
    embeddings = embed_texts(texts)

    chunk_ids, metadatas = [], []
    for (content, source, profile_key, category), embedding in zip(_SEED_ITEMS, embeddings):
        min_d, max_d, min_a, max_a = _PROFILES[profile_key]
        days = random.randint(min_d, max_d)
        last_accessed = now - timedelta(days=days)
        created_at = last_accessed - timedelta(days=random.randint(1, 7))
        access_count = random.randint(min_a, max_a)

        cid = insert_chunk(
            content=content,
            source_file=source,
            complexity_score=round(random.uniform(0.4, 0.8), 2),
            user_id=user_id,
            created_at=created_at,
            last_accessed=last_accessed,
            access_count=access_count,
        )
        # Pre-assign category — skip the LLM classifier entirely so it works without a Groq key.
        update_chunk_category(cid, category)
        chunk_ids.append(cid)
        metadatas.append({"user_id": user_id, "chunk_id": cid, "source_file": source})

    add_chunks(chunk_ids, embeddings, metadatas)

    return {
        "message": f"Seeded {len(chunk_ids)} demo chunks across strong/fading/weak/critical profiles and 5 categories.",
        "seeded": len(chunk_ids),
    }
