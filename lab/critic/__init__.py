"""Automated Quant Critic: ordered fail-closed gate that produces verdicts. Paper only."""
from lab.critic.checks import CriticConfig, CriticInputs, SensitivityResult
from lab.critic.verdict import render_verdict_md, run_critic, update_approved_list

__all__ = [
    "CriticConfig",
    "CriticInputs",
    "SensitivityResult",
    "render_verdict_md",
    "run_critic",
    "update_approved_list",
]
