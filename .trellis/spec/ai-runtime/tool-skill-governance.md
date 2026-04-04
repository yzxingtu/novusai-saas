# Tool And Skill Governance

## Goal

Tools and skills should be routed deliberately, with explicit cost awareness.

## Rules

- skill routing and tool routing are different decisions
- neither layer should widen context or candidate actions without a clear payoff
- overlapping skills must be resolved by scope, not by stacking all of them
- explicit mutual exclusion is better than prompt-era “best effort” arbitration

## Budget Rules

- cap candidate tools per turn
- cap candidate skills per turn
- do not expose tools that are irrelevant to the active intent
- do not expose whole tool families for convenience

## Trigger Rules

- use a skill only when the task matches its scope
- do not trigger deep workflow mechanics for routine tasks
- do not load large reference bundles by default

## Prohibited Patterns

- recursive skill escalation
- tool exposure without minimal-necessity filtering
- duplicated rule bodies across `.trellis`, `.claude`, `.agents`, and `.cursor`
