# ODIN — Personal Internet Intelligence Engine

## 1. Project Overview

ODIN is a personal AI-powered internet intelligence and social media assistant.

The goal is NOT to build a generic AI content generator.

ODIN continuously monitors the internet, discovers emerging topics and news, identifies high-value opportunities, evaluates their viral/social potential, learns the user's personal writing style and historical performance, and generates platform-specific content recommendations.

The long-term vision:

> "ODIN watches the internet for me, understands what matters, predicts what is worth talking about, creates content in my style, and learns from the results."

The first target platform is X (Twitter), but the architecture MUST NOT be X-specific.

ODIN must be designed from day one as a multi-source, multi-platform intelligence system.

---

# 2. Core Principles

## 2.1 Event-first architecture

Do NOT treat every article, tweet, Reddit post, or RSS item as a separate trend.

Multiple sources may describe the same real-world event.

Example:

- OpenAI official blog
- TechCrunch
- Hacker News
- Reddit
- X
- GitHub

may all discuss the same event.

ODIN must cluster these into a single canonical:

`Event`

Example:

```text
Event:
"OpenAI launches new model"

Sources:
- OpenAI
- TechCrunch
- Hacker News
- Reddit
- X
This prevents duplicate analysis and duplicate content generation.
3. Main Architecture
The system should be structured around these major engines:
                    ODIN
                     |
        +------------+-------------+
        |                          |
   DATA INGESTION             USER PROFILE
        |                          |
        v                          v
   EVENT ENGINE              PERSONAL ENGINE
        |                          |
        +------------+-------------+
                     |
                     v
              TREND ENGINE
                     |
                     v
          OPPORTUNITY ENGINE
                     |
          +----------+----------+
          |                     |
          v                     v
   VIRAL PREDICTION       CONTENT ENGINE
          |                     |
          +----------+----------+
                     |
                     v
             PLATFORM ADAPTERS
                     |
          +----------+----------+
          |          |          |
          v          v          v
          X       LinkedIn    Reddit
4. Data Sources
The initial implementation should support:
Tier 1
RSS feeds
X API
Hacker News
Reddit
GitHub
News APIs where appropriate
Tier 2
Prepare adapters/interfaces for:
Google News
Product Hunt
TechCrunch
The Verge
Ars Technica
SecurityWeek
BleepingComputer
official company blogs
CVE/NVD feeds
developer blogs
Do NOT hard-code the application around a specific source.
Every source must implement a common interface.
Example conceptual interface:
class SourceAdapter:
    async def fetch(self):
        ...

    async def normalize(self, item):
        ...

    async def health_check(self):
        ...
5. Canonical Data Model
Everything collected from the internet should first become a normalized ContentItem.
Example:
{
  "id": "...",
  "source": "rss",
  "source_name": "TechCrunch",
  "source_item_id": "...",
  "url": "...",
  "title": "...",
  "text": "...",
  "author": "...",
  "published_at": "...",
  "language": "en",
  "media": [],
  "engagement": {},
  "metadata": {}
}
Then content items are clustered into Event objects.
Example:
{
  "id": "...",
  "title": "OpenAI launches new model",
  "summary": "...",
  "first_seen_at": "...",
  "last_seen_at": "...",
  "sources": [],
  "content_items": [],
  "entities": [],
  "topics": [],
  "velocity": {},
  "engagement": {},
  "trend_score": 0,
  "opportunity_score": 0,
  "confidence_score": 0
}
6. Event Detection
ODIN must identify whether two content items refer to the same event.
Use a combination of:
embeddings
named entities
keywords
timestamps
semantic similarity
source information
URLs
explicit references
Do NOT rely only on embeddings.
Example:
Article A:
"OpenAI announces GPT-X"

Tweet B:
"OpenAI just dropped GPT-X"

Reddit C:
"Thoughts on the new OpenAI GPT-X?"

These should become one event.
7. Event Lifecycle
Every event has a lifecycle:
DISCOVERED
    ↓
VERIFIED
    ↓
RISING
    ↓
TRENDING
    ↓
SATURATED
    ↓
DECLINING
    ↓
ARCHIVED
ODIN should continuously update event state.
8. Trend Detection
Trend detection is one of the most important components.
Do NOT rank topics only by total engagement.
A topic with 1 million mentions but declining activity may be less valuable than a topic with 2,000 mentions growing 500% per hour.
Calculate:
mention velocity
velocity acceleration
engagement velocity
cross-platform spread
source diversity
novelty
growth rate
competition
saturation
recency
Example:
Topic: AI Agents

mentions:
10:00 → 100
10:30 → 230
11:00 → 700
11:30 → 2100
This should have high momentum.
9. Trend Score
Create a normalized 0-100 score.
Initial formula can be:
TrendScore =
    0.30 * Velocity
  + 0.20 * Acceleration
  + 0.15 * EngagementVelocity
  + 0.15 * CrossPlatformSpread
  + 0.10 * Novelty
  + 0.10 * SourceDiversity
These weights are NOT permanent.
The architecture must allow future ML-based scoring.
10. User Profile
ODIN is a PERSONAL assistant.
It must learn the user's interests.
Store:
preferred topics
disliked topics
preferred languages
preferred platforms
expertise
historical engagement
preferred posting times
preferred content types
writing style
vocabulary
tone
sentence structure
hook patterns
humor level
technical depth
controversy level
preferred post length
Example:
{
  "topics": {
    "AI": 0.94,
    "Cybersecurity": 0.96,
    "Open Source": 0.92,
    "Docker": 0.85,
    "Programming": 0.88
  },
  "style": {
    "tone": "direct",
    "technicality": 0.82,
    "humor": 0.31,
    "controversiality": 0.61,
    "uses_questions": true
  }
}
11. User Writing Style
Do NOT start with fine-tuning.
First create a style fingerprint from historical posts.
Analyze:
average length
sentence length
punctuation
emojis
capitalization
vocabulary
technical terminology
opening hooks
rhetorical questions
list usage
paragraph structure
tone
opinions
storytelling
humor
CTA patterns
Use embeddings to identify clusters of successful posts.
12. Historical Performance Model
For every historical post store:
post_id
platform
created_at
text
topic
content_type
impressions
likes
replies
reposts
quotes
bookmarks
shares
profile_clicks
followers_at_post_time
media_type
contains_link
hour
day_of_week
Where possible also store time-series metrics:
5m
15m
30m
1h
3h
6h
12h
24h
This allows ODIN to learn performance trajectories.
13. Personal Performance Score
ODIN should answer:
"Does this type of content work for THIS user?"

Example:
Cybersecurity + contrarian opinion
Personal score: 94

AI tutorial
Personal score: 71

Breaking news
Personal score: 83

Long technical thread
Personal score: 52
This is more important than generic virality.
14. Opportunity Score
Trend score and opportunity score are NOT the same.
TrendScore answers:
"Is this topic currently growing?"

OpportunityScore answers:
"Should THIS USER talk about this topic RIGHT NOW?"

Use:
OpportunityScore =
    TrendScore
  + PersonalRelevance
  + ContentGap
  + TimeSensitivity
  + LowCompetition
  + SourceConfidence
Normalize to 0-100.
Example:
Event:
New cybersecurity vulnerability

Trend Score:          91
Personal relevance:   96
Competition:          42
Time sensitivity:     98
Content gap:          88
Source confidence:    97

Opportunity Score:    95
15. Source Confidence
Never blindly trust viral content.
Calculate source confidence.
Examples:
Official source              1.00
Established publication      0.90
Known journalist             0.82
Established blog             0.75
Reddit                        0.60
Unknown social account       0.25
These are initial heuristics, not permanent truth.
Confidence should consider:
source reputation
corroboration
number of independent sources
official confirmation
publication history
contradictions
A viral but unverified event must be clearly marked.
Example:
Viral Potential: 94
Confidence: 54

⚠ High viral potential but insufficient verification.
16. X Algorithm Simulation
ODIN should incorporate the public X recommendation algorithm.
Important:
DO NOT claim that ODIN exactly reproduces X's production algorithm.
The UI must use language such as:
X Algorithm Simulation
or:
Public X Algorithm Estimate
Never:
Guaranteed X Score
The system should track the public X algorithm repository/version used for simulation.
Store:
algorithm_version
algorithm_commit
scoring_version
The simulator should model public concepts including:
predicted engagement actions
likes
replies
reposts
bookmarks
clicks
profile clicks
shares
follows
negative actions
visibility filtering
author diversity
out-of-network considerations
ranking
Do not reduce the X system to:
likes * weight
The public algorithm uses predicted action probabilities.
17. Action Prediction
The scoring system should conceptually operate on:
P(like | user, post)
P(reply | user, post)
P(repost | user, post)
P(bookmark | user, post)
P(click | user, post)
P(profile_click | user, post)
P(follow | user, post)
P(negative_action | user, post)
Then combine those probabilities using the publicly documented scoring approach where applicable.
If exact production model behavior cannot be reproduced, clearly label the result as an estimate.
18. Personal Viral Score
The final score should combine:
X Algorithm Simulation
Personal Performance
Trend Momentum
Topic Relevance
Novelty
Content Quality
Source Confidence
Example:
X Simulation:        84
Personal Fit:        91
Trend Momentum:      93
Novelty:             78
Source Confidence:   97

FINAL SCORE:         89/100
19. Tweet Tester
The user must be able to paste any text.
Example:
[ Paste your tweet ]

[ ANALYZE ]
Return:
VIRAL POTENTIAL        84/100

X SIMULATION            81
PERSONAL FIT            92
TREND FIT               88
NOVELTY                  71

REPLY POTENTIAL          89
BOOKMARK POTENTIAL       83
NEGATIVE RISK            12
Then explain:
Why?

+ Strong hook
+ High relevance to current topic
+ Matches your successful historical posts

- Low novelty
- Similar framing used frequently
20. Content Generator
When an event has a high OpportunityScore, ODIN should generate multiple angles.
For example:
1. Breaking News
2. Contrarian Opinion
3. Technical Explanation
4. Personal Take
5. Question / Discussion
6. Educational
Do NOT simply generate 10 paraphrases.
Each candidate must represent a distinct strategic angle.
21. Candidate Ranking
For each generated candidate:
candidate_id
text
angle
platform
trend_score
personal_score
viral_score
source_confidence
novelty_score
risk_score
Rank them.
Example:
#1 Contrarian      92
#2 Technical       88
#3 Breaking News   81
22. Content Gap Detection
One of ODIN's key features should be:
"What is everyone talking about, but nobody is explaining correctly?"

Detect:
repeated narratives
missing technical explanation
unanswered questions
misunderstood topics
conflicting information
underserved perspectives
Example:
Everyone says:
"AI agents are replacing developers."

Content gap:
Nobody is discussing the infrastructure cost.

Suggested angle:
"The real bottleneck for AI agents isn't intelligence. It's infrastructure."
23. News-to-Post Pipeline
The full workflow should be:
Internet
   ↓
Sources
   ↓
ContentItems
   ↓
Event Detection
   ↓
Event Clustering
   ↓
Verification
   ↓
Trend Analysis
   ↓
Personal Relevance
   ↓
Opportunity Score
   ↓
Content Angles
   ↓
AI Generation
   ↓
Viral Simulation
   ↓
Top Candidates
   ↓
User Approval
   ↓
Publish
   ↓
Collect Metrics
   ↓
Compare Prediction vs Reality
   ↓
Model Update
24. Human-in-the-loop
ODIN should NOT automatically publish by default.
The default behavior:
DETECT
↓
ANALYZE
↓
GENERATE
↓
SCORE
↓
ASK USER
↓
PUBLISH
The user must explicitly approve publication.
Automatic publishing can be implemented later as an opt-in feature.
25. Platform Adapters
Create a generic interface:
class PlatformAdapter:
    async def publish(self, content):
        ...

    async def get_metrics(self, post_id):
        ...

    async def validate(self, content):
        ...

    async def format(self, content):
        ...
Implement:
XAdapter
RedditAdapter
LinkedInAdapter
eventually.
Each platform must have separate:
content formatting
scoring
character limits
engagement prediction
publishing logic
analytics
Do NOT assume that what works on X works on LinkedIn or Reddit.
26. RSS System
RSS is a first-class data source.
Implement:
feed registry
feed validation
polling
ETag support
Last-Modified support
deduplication
retry logic
failure tracking
feed health
language detection
Example configuration:
feeds:
  - name: OpenAI
    url: https://...
    category: ai
    priority: high

  - name: Hacker News
    url: https://...
    category: technology
    priority: high
Do not hard-code feed URLs inside application logic.
27. Source Management
The UI should allow the user to:
add RSS source
remove RSS source
enable/disable source
assign topic
assign priority
set polling interval
see source health
Example:
OpenAI Blog          ● Healthy
Hacker News          ● Healthy
BleepingComputer     ● Healthy
Custom RSS           ● Error
28. Topics
Users must be able to define topics.
Example:
AI
Cybersecurity
OSINT
Open Source
Docker
Linux
Programming
AI Agents
Developer Tools
Each topic should have:
name
keywords
semantic_embedding
priority
enabled
Allow negative keywords.
Example:
AI

include:
LLM
agents
OpenAI
Anthropic

exclude:
crypto
NFT
29. Dashboard
The main dashboard should show:
TODAY

🔥 TOP OPPORTUNITIES

1. New OpenAI release
   Opportunity: 96

2. New CVE
   Opportunity: 93

3. GitHub project exploding
   Opportunity: 89
Also:
TRENDING TOPICS
YOUR PERFORMANCE
DRAFTS
RECENT POSTS
30. Event Detail Page
Clicking an event should show:
EVENT

New OpenAI model

First detected:
17:02

Sources:
OpenAI
TechCrunch
Hacker News
Reddit
X

Trend:
████████████ 93

Velocity:
+312%

Confidence:
97%

Competition:
Low

Your relevance:
96%

Opportunity:
95%
Then:
WHY THIS MATTERS

...

WHAT PEOPLE ARE SAYING

...

CONTENT GAPS

...

GENERATE CONTENT
31. "What Should I Post Now?"
This should be a core feature.
The system analyzes the current environment and returns:
WHAT SHOULD I POST NOW?

#1
New cybersecurity vulnerability

Opportunity: 96
Time sensitivity: 98
Personal relevance: 97

Recommended action:
POST NOW

#2
OpenAI update

Opportunity: 91

Recommended action:
POST WITHIN 30 MIN

#3
Docker discussion

Opportunity: 78

Recommended action:
WAIT
32. Notifications
Allow:
high opportunity event
breaking news
trend spike
source failure
high-confidence story
recommended post
post performance anomaly
Example:
🔥 ODIN detected a high-value opportunity.

Cybersecurity topic increased 287% in 40 minutes.

Opportunity Score: 94

Open ODIN
33. Feedback Loop
This is critical.
After publication:
Prediction
      ↓
Actual metrics
      ↓
Prediction error
      ↓
Model update
Example:
Predicted impressions:
8,000

Actual:
21,300

Prediction error:
+166%

Reason:
Underestimated reply probability.
Store all predictions.
Never overwrite old predictions.
34. Model Versioning
Every prediction must have:
model_version
algorithm_version
feature_version
timestamp
This makes historical evaluation possible.
35. Evaluation
Build an evaluation framework.
Metrics:
MAE
RMSE
ranking accuracy
calibration
precision@K
recall@K
top candidate success rate
For content ranking:
Did the system's #1 recommendation actually outperform #2 and #3?
This matters more than absolute score accuracy.
36. Security
Secrets must NEVER be committed.
Use:
.env
for:
X API keys
Reddit API credentials
OpenAI API key
other provider keys
Add .env to .gitignore.
Use environment variables.
37. Database
Use PostgreSQL.
Recommended extensions:
pgvector
Core tables:
users
sources
source_items
events
event_sources
topics
event_topics
user_topics
posts
post_metrics
post_predictions
style_profiles
content_candidates
platforms
algorithm_versions
notifications
model_runs
Use migrations.
Never manually mutate production schema.
38. Backend
Preferred:
Python
FastAPI
PostgreSQL
Redis
Celery or ARQ
API structure:
/api/v1/sources
/api/v1/events
/api/v1/trends
/api/v1/topics
/api/v1/posts
/api/v1/predictions
/api/v1/content
/api/v1/profile
/api/v1/analytics
39. Frontend
Preferred:
Next.js
TypeScript
TailwindCSS
shadcn/ui
Design should feel like:
intelligence dashboard
modern security platform
premium developer tool
Avoid generic "AI SaaS" design.
The product should feel analytical and serious.
40. Brand
Product name:
ODIN
Concept:
Odin watches the world.

The mythology reference is intentional.
Odin is associated with wisdom, knowledge, observation, and his ravens Huginn and Muninn gathering information from the world.
The product should use this concept subtly.
Do not overuse Viking decorations.
Avoid cliché:
giant Viking helmets
cartoon ravens
fantasy UI
Prefer:
dark intelligence aesthetic
subtle runic geometry
clean typography
data visualization
signal indicators
radar / observation motifs
41. API Provider Abstraction
Do not couple the application to one LLM provider.
Create:
class LLMProvider:
    async def generate(...)
    async def embed(...)
    async def classify(...)
Implement providers separately.
Potential providers:
OpenAI
Anthropic
local models
The application should be able to switch providers through configuration.
42. LLM Usage Rules
LLMs should be used for:
summarization
classification
entity extraction
semantic interpretation
content generation
style analysis
event understanding
LLMs should NOT be the only mechanism for:
trend scoring
viral scoring
numerical ranking
source confidence
historical performance prediction
Use deterministic/statistical/ML systems for numerical scoring where possible.
43. Cost Control
Do not send every RSS article to an expensive LLM.
Pipeline:
Raw ingestion
    ↓
Cheap filtering
    ↓
Deduplication
    ↓
Embedding
    ↓
Event clustering
    ↓
Only important events
    ↓
LLM analysis
Use caching.
Batch operations when possible.
44. Observability
Every pipeline should be observable.
Track:
ingestion latency
source failures
event clustering rate
LLM cost
API cost
processing time
prediction accuracy
publishing failures
Use structured logs.
45. Testing
Write tests for:
RSS parsing
source normalization
deduplication
event clustering
topic matching
trend calculation
score calculation
platform formatting
prediction pipeline
Do not rely only on manual testing.
46. Development Rules
When implementing features:
Understand the existing architecture first.
Do not rewrite working components unnecessarily.
Keep modules small.
Use typed interfaces.
Write tests for important logic.
Never hard-code secrets.
Never hard-code external source configuration.
Keep platform-specific logic isolated.
Keep scoring systems versioned.
Prefer explainable scoring over black-box scoring.
Document non-obvious decisions.
Keep the system extensible.
47. MVP Scope
Do NOT attempt to implement everything at once.
Phase 1:
PostgreSQL
FastAPI
Next.js
RSS ingestion
Hacker News ingestion
GitHub ingestion
Event clustering
Topic system
Trend scoring
Basic dashboard
Phase 2:
X API
Reddit
User profile
Historical post import
Style analysis
Content generation
Phase 3:
X algorithm simulation
Personal performance model
Tweet tester
Opportunity scoring
Phase 4:
Publish workflow
Metrics collection
Prediction vs actual
Self-improving model
Phase 5:
LinkedIn
More news sources
Advanced recommendation system
Automated notifications
48. First Development Task
Before writing large amounts of code:
Inspect the repository.
Determine whether an existing application exists.
Create a technical architecture.
Create the initial folder structure.
Create Docker development environment.
Create PostgreSQL configuration.
Create FastAPI backend.
Create Next.js frontend.
Implement database migrations.
Implement RSS source model.
Implement one RSS adapter.
Implement Hacker News adapter.
Implement normalized ContentItem model.
Implement Event model.
Implement basic event deduplication.
Implement basic TrendScore.
Create dashboard showing detected events.
Do NOT implement the entire product in one step.
Build incrementally.
49. Definition of Done for MVP
The MVP is successful when:
ODIN can continuously ingest RSS feeds.
ODIN can ingest Hacker News.
ODIN normalizes incoming content.
ODIN identifies duplicate stories.
ODIN clusters stories into events.
ODIN calculates trend momentum.
ODIN ranks events.
ODIN displays the highest opportunity events.
A user can click an event and inspect its sources.
The system is ready for X/Reddit adapters.
The architecture does not need to be rewritten to add another source.
50. Important Product Philosophy
ODIN is NOT:
a ChatGPT wrapper
a tweet generator
a news reader
an RSS reader
a generic social media scheduler
a simple viral score calculator
ODIN IS:
A personal intelligence system that continuously observes the internet, understands emerging events, predicts opportunities, generates platform-specific content, and learns from the user's results.

The most important loop is:
OBSERVE
   ↓
UNDERSTAND
   ↓
PREDICT
   ↓
RECOMMEND
   ↓
CREATE
   ↓
PUBLISH
   ↓
MEASURE
   ↓
LEARN
   ↓
OBSERVE AGAIN
Build toward this loop.
51. Coding Instruction
When asked to implement a feature:
First inspect the relevant code.
Explain the implementation plan briefly.
Implement the smallest correct version.
Add tests.
Run tests.
Fix errors.
Report what changed.
Do not create fake implementations just to satisfy interfaces.
Do not leave TODO placeholders for core functionality.
If an external API is unavailable, create a clean adapter and a mock implementation for development.
52. Final Objective
The final ODIN experience should feel like this:
The user opens ODIN.
ODIN says:
Good evening.

I found 7 emerging opportunities.

🔥 3 are highly relevant to you.

1. New cybersecurity vulnerability
   Opportunity: 96
   Best time: NOW

2. Open-source AI project exploding on GitHub
   Opportunity: 92
   Best time: within 45 minutes

3. New AI model discussion
   Opportunity: 88
The user clicks #1.
ODIN explains:
WHY THIS MATTERS

The topic grew 312% in 45 minutes.

It is being discussed across:
X
Reddit
Hacker News
Security blogs

Your relevance: 97

Content gap:
Most posts explain WHAT happened.
Very few explain WHY developers should care.
Then:
GENERATE CONTENT
ODIN creates:
1. Contrarian
2. Technical
3. Breaking News
4. Educational
Each gets:
Viral Potential
Personal Fit
Trend Fit
Novelty
Risk
Source Confidence
The user chooses one.
ODIN publishes it.
Later:
PREDICTED: 8,200 impressions
ACTUAL:    19,400 impressions

ODIN learned:

Your audience responds strongly to
technical + breaking-news combinations.

Personal model updated.
That is the product we are building.
Do not lose sight of this objective.
