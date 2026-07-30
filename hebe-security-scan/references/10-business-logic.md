# Business Logic

**The hardest category to detect automatically — no automated scanner catches this.** It requires understanding the domain, not just the code.

## How to think about it

For every flow that generates value (money, permission, access, state), ask:

- **Is there a counterpart?** Does a refund zero out the associated commission? Does a withdrawal block a pending refund? Does a cancellation reverse the credit that was granted?
- **Does the state machine close?** Are illegal transitions rejected (paying an already-paid order, withdrawing twice, approving something already approved)?
- **Can the origin be traced?** If a user gained balance, where did it come from? Is there a gap that creates value out of nothing?
- **Self-reference:** can a user be their own affiliate? apply their own coupon? approve their own request?
- **Order / timing:** can an attacker exploit a window (e.g. a 30-minute refund grace period) to extract value before the system reverses it?

## Real-world example (source video)

An affiliate signs up on a course platform → generates their own coupon → buys their own course using that coupon → withdraws the affiliate commission on that sale → requests a refund within the refund window (30 minutes). Net result: the platform pays out a commission, refunds the purchase, and the attacker keeps the cash. **Infinite money**, and it required zero technical exploit — just walking through legitimate features in an order the designers never modeled. Manual detection doesn't scale here; it needs an explicit rule plus review, because each individual step (sign up as affiliate, create coupon, buy a course, request refund) is a completely normal, allowed action.

## Why this is the category AI gets wrong the most, and automated scanners can't catch

Business logic bugs don't look like bugs to a static analyzer or a fuzzer — there's no malformed input, no injection, no missing auth check. Every individual API call is authorized and valid. The vulnerability only exists at the level of the *sequence* of otherwise-legitimate operations and the *missing counterpart* between them (a refund that doesn't claw back the commission it funded). An AI coding assistant, prompted feature-by-feature, tends to implement each flow (affiliate signup, coupon creation, purchase, refund) correctly in isolation — and never models the interaction between them, because nobody asked it to. This is exactly the class of bug that separated the best result in the source video (0 vulnerabilities) from the rest: the senior dev using TDD explicitly wrote tests that modeled cross-feature abuse, rather than trusting that each feature being individually correct meant the system was correct.

## Fixes

- **Explicit state, validated transitions, enforced server-side.** Model the state machine (e.g. order: `pending → paid → refunded`, never `refunded → refunded` or `paid → paid`) and reject illegal transitions outright.
- **Rate limit transactions**, and add suspicious-pattern detection: same IP buying and refunding, a brand-new signup followed by an immediate withdrawal.
- **Hold payouts/commissions until the refund window closes.** A withdrawal or commission payout should never be possible while a refund is still available for the underlying purchase.
- **If using Stripe: enable Stripe Radar** for fraud detection — it catches patterns a hand-rolled rule set won't.
- Trace balance origin end-to-end: every credit a user holds should be attributable to a specific, still-valid source transaction.
