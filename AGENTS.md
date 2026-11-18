# Agent instructions

- Use the Alpaca historical stock-bars endpoint for data access. Keep all integrations read-only. The CLI simulates fills locally.
- Read credentials from the environment. Keep keys, account information, downloaded datasets and research outputs out of git.
- Keep the symbol universe configurable. Validate bar dates and prices before simulations and follow pagination through the last page.
- Preserve close-to-next-open execution and document price adjustments, assumptions and costs.
- Use synthetic fixtures for offline checks. For research, define the rules first, document trial counts, use time-ordered validation and keep the final holdout untouched.
