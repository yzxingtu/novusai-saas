# Intent Routing

## Goals

- produce stable structured intents for the same user turn
- separate intent planning from tool selection
- keep candidate tools small and explicit

## Rules

- Plan user work as one or more intents, not one “primary family” string.
- Choose execution path from intent count and risk:
  - one bounded intent -> `fast`
  - one to two clear intents -> `normal`
  - three or more intents, or cross-capability mixed work -> `deep`
- Tool routing happens after intent planning.
- Candidate tools must be minimized before the model sees them.
- Do not hand the model large mixed-family tool sets and hope an optimizer fixes it later.

## Multi-Intent

For mixed requests:

- split the requested work into explicit intents
- track completion per intent
- retry only the unfinished intent
- return partial results when one intent fails after budget is exhausted

## Prohibited Patterns

- regex-order decides primary routing
- tool family drift during recovery
- retrying the entire turn when only one intent is incomplete
