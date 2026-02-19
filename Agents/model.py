from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Account:
    id: str
    balance: float
    currency: str = "USD"
    min_balance: float = 0.0
    sweep_threshold: float = 0.0
    daily_limit: float = float("inf")


@dataclass
class SweepAction:
    from_account: str
    to_account: str
    amount: float
    timing: str | None = None
    reason: str | None = None


def optimize_sweeps(accounts: List[Account], concentration_account_id: str) -> List[SweepAction]:
    actions: List[SweepAction] = []
    accounts_by_id = {a.id: a for a in accounts}
    if concentration_account_id not in accounts_by_id:
        raise ValueError("concentration account id not found")
    for a in accounts:
        if a.id == concentration_account_id:
            continue
        available = a.balance - a.min_balance
        if available <= 0:
            continue
        if a.balance <= a.sweep_threshold:
            continue
        sweep_amount = min(available, a.balance - a.sweep_threshold, a.daily_limit)
        if sweep_amount <= 0:
            continue
        actions.append(SweepAction(from_account=a.id, to_account=concentration_account_id, amount=round(sweep_amount, 2)))
    return actions
