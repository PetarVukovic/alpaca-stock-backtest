"""Per-fill costs, with a US equity tick of one cent."""

from lab.contracts import Costs

THIN = {"MRAM", "ACMR", "DRAM", "SKHY", "SNDK"}


def effective_costs(costs, ticker):
    if (
        costs.round_trip_bps < 5
        or costs.tick_per_side < 1
        or costs.stress_multiplier < 1
    ):
        raise ValueError("Costs below lab floor")
    return costs.model_copy(
        update={
            "stress_multiplier": costs.stress_multiplier * (2 if ticker in THIN else 1)
        }
    )


def fill_price(price, side, costs: Costs):
    if price <= 0 or side not in {"buy", "sell"}:
        raise ValueError("Invalid fill")
    delta = (
        price * costs.round_trip_bps / 20000 + 0.01 * costs.tick_per_side
    ) * costs.stress_multiplier
    result = price + delta if side == "buy" else price - delta
    if result <= 0:
        raise ValueError("Costs exceed price")
    return result
