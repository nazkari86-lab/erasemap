# ruff: noqa: E501
"""Safe local control-plane model for a synthetic 512-customer KYC bank.

The module is intentionally limited to generated data and simulated connectors.
It gives the web demonstration a real state machine, explicit permissions, a
dry-run plan, and repeatable proof records without impersonating a bank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import RLock
from typing import Any


class RequestStage(StrEnum):
    NO_REQUEST = "NO_REQUEST"
    REQUESTED = "REQUESTED"
    VISIBLE_COPIES_ERASED = "VISIBLE_COPIES_ERASED"
    RECURRENCE_OBSERVED = "RECURRENCE_OBSERVED"
    RECOVERY_LOCALIZED = "RECOVERY_LOCALIZED"
    CUT_APPLIED = "CUT_APPLIED"
    VERIFIED = "VERIFIED"


@dataclass(frozen=True, slots=True)
class ConnectorDefinition:
    id: str
    name: str
    artifact_label: str
    methods: tuple[str, ...]
    color: str


@dataclass(frozen=True, slots=True)
class SyntheticCustomer:
    customer_id: str
    display_name: str
    account_alias: str
    risk_tier: str
    is_demo_subject: bool = False


@dataclass(slots=True)
class DeletionCase:
    customer_id: str
    stage: RequestStage = RequestStage.NO_REQUEST
    event_log: list[str] = field(default_factory=list)


CONNECTORS: tuple[ConnectorDefinition, ...] = (
    ConnectorDefinition(
        "postgres",
        "PostgreSQL KYC",
        "KYC profile",
        ("scan profile", "delete subject row", "verify absence"),
        "#4ea6ff",
    ),
    ConnectorDefinition(
        "keycloak",
        "Keycloak IAM",
        "Identity & sessions",
        ("list sessions", "revoke subject", "verify identity state"),
        "#9e7bff",
    ),
    ConnectorDefinition(
        "redis",
        "Redis cache",
        "Auth cache",
        ("scan key", "invalidate subject key", "verify miss"),
        "#ff6d75",
    ),
    ConnectorDefinition(
        "qdrant",
        "Qdrant vectors",
        "Face template",
        ("query vector", "delete point", "verify absence"),
        "#62d6a1",
    ),
    ConnectorDefinition(
        "minio",
        "MinIO backup",
        "Encrypted snapshot",
        ("inspect manifest", "exclude subject snapshot", "block restore", "verify replay"),
        "#ffc66d",
    ),
)

ARTIFACTS: tuple[tuple[str, str, str, str], ...] = (
    ("postgres", "kyc_profile", "KYC profile", "Customer record"),
    ("keycloak", "identity", "Identity & sessions", "Authentication derivative"),
    ("redis", "auth_cache", "Auth cache", "Fast-login copy"),
    ("qdrant", "face_template", "Face template", "Biometric vector"),
    ("minio", "encrypted_snapshot", "Encrypted backup", "Recovery carrier"),
    ("model", "fraud_model_channel", "Fraud-model channel", "Model influence"),
)

_NEXT_ACTION: dict[RequestStage, str] = {
    RequestStage.NO_REQUEST: "create-request",
    RequestStage.REQUESTED: "delete-visible",
    RequestStage.VISIBLE_COPIES_ERASED: "simulate-recovery",
    RequestStage.RECURRENCE_OBSERVED: "run-probes",
    RequestStage.RECOVERY_LOCALIZED: "apply-exact-cut",
    RequestStage.CUT_APPLIED: "verify-replay",
}

_ACTION_LABELS: dict[str, str] = {
    "create-request": "Create deletion request",
    "delete-visible": "Delete visible copies",
    "simulate-recovery": "Simulate scheduled backup restore",
    "run-probes": "Run bounded hidden-path probes",
    "apply-exact-cut": "Apply exact deletion cut",
    "verify-replay": "Replay and verify certificate",
}


class SyntheticBankControlPlane:
    """Stateful but deterministic local bank sandbox with 500+ synthetic clients."""

    def __init__(self, *, customer_count: int = 512) -> None:
        if customer_count < 500:
            raise ValueError("customer_count must be at least 500")
        self._lock = RLock()
        self._customers = self._build_customers(customer_count)
        self._cases: dict[str, DeletionCase] = {
            customer.customer_id: DeletionCase(customer.customer_id)
            for customer in self._customers
        }
        self._customer_by_id = {customer.customer_id: customer for customer in self._customers}
        self._demo_customer_id = "KZ-DEMO-042"

    @staticmethod
    def _build_customers(customer_count: int) -> tuple[SyntheticCustomer, ...]:
        customers: list[SyntheticCustomer] = []
        for index in range(1, customer_count + 1):
            customer_id = f"KZ-SYN-{index:04d}"
            customers.append(
                SyntheticCustomer(
                    customer_id=customer_id,
                    display_name=f"Synthetic customer {index:03d}",
                    account_alias=f"acct-syn-{index:04d}",
                    risk_tier=("LOW", "MEDIUM", "HIGH")[index % 3],
                )
            )
        demo_index = 41
        customers[demo_index] = SyntheticCustomer(
            customer_id="KZ-DEMO-042",
            display_name="Amina S. (synthetic)",
            account_alias="acct-demo-042",
            risk_tier="MEDIUM",
            is_demo_subject=True,
        )
        return tuple(customers)

    @property
    def demo_customer_id(self) -> str:
        return self._demo_customer_id

    @property
    def customer_count(self) -> int:
        return len(self._customers)

    def manifest(self) -> dict[str, Any]:
        return {
            "schema_version": "erasemap-synthetic-bank-control-plane-v1",
            "system_name": "Orda Bank — local synthetic KYC control plane",
            "scope": (
                "Local synthetic control plane. All 512 customers, records, artifacts, connectors, "
                "actions and receipts are generated; no bank, eGov, Face ID, account, or biometric "
                "data is connected."
            ),
            "customer_count": self.customer_count,
            "registered_artifact_count": self.customer_count * len(ARTIFACTS),
            "demo_customer_id": self.demo_customer_id,
            "connectors": [
                {
                    "id": connector.id,
                    "name": connector.name,
                    "artifact_label": connector.artifact_label,
                    "methods": list(connector.methods),
                    "color": connector.color,
                    "mode": "SYNTHETIC_LOCAL_ADAPTER",
                }
                for connector in CONNECTORS
            ],
            "required_approval": True,
            "claim_boundary": (
                "The control plane demonstrates connector contracts and a deletion lifecycle. "
                "A production integration requires organization approval, credentials, field mappings, "
                "complete topology registration and an authorized evaluation."
            ),
        }

    def list_customers(self, *, query: str = "", limit: int = 80) -> list[dict[str, Any]]:
        if limit < 1 or limit > 512:
            raise ValueError("limit must be between 1 and 512")
        needle = query.strip().lower()
        with self._lock:
            selected = [
                customer
                for customer in self._customers
                if not needle
                or needle in customer.customer_id.lower()
                or needle in customer.display_name.lower()
                or needle in customer.account_alias.lower()
            ][:limit]
            return [self._customer_summary(customer) for customer in selected]

    def overview(self) -> dict[str, Any]:
        with self._lock:
            counts = {stage.value: 0 for stage in RequestStage}
            for case in self._cases.values():
                counts[case.stage.value] += 1
            return {
                **self.manifest(),
                "request_counts": counts,
                "retained_customer_count": self.customer_count - 1,
                "connector_health": [
                    {"id": connector.id, "status": "READY", "mode": "SYNTHETIC_LOCAL_ADAPTER"}
                    for connector in CONNECTORS
                ],
            }

    def customer_snapshot(self, customer_id: str) -> dict[str, Any]:
        with self._lock:
            customer = self._customer(customer_id)
            case = self._cases[customer_id]
            return {
                "customer": self._customer_summary(customer),
                "stage": case.stage.value,
                "verdict": self._verdict(case.stage),
                "artifacts": self._artifacts(case.stage),
                "next_action": _NEXT_ACTION.get(case.stage),
                "next_action_label": _ACTION_LABELS.get(_NEXT_ACTION.get(case.stage, "")),
                "event_log": list(case.event_log),
                "dry_run": self._dry_run(case.stage),
                "retained_customer_count": self.customer_count - 1,
            }

    def execute_action(self, customer_id: str, action: str) -> dict[str, Any]:
        with self._lock:
            self._customer(customer_id)
            case = self._cases[customer_id]
            expected = _NEXT_ACTION.get(case.stage)
            if expected is None:
                raise ValueError("deletion lifecycle is already verified")
            if action != expected:
                raise ValueError(f"expected action {expected!r}, received {action!r}")
            case.stage = {
                "create-request": RequestStage.REQUESTED,
                "delete-visible": RequestStage.VISIBLE_COPIES_ERASED,
                "simulate-recovery": RequestStage.RECURRENCE_OBSERVED,
                "run-probes": RequestStage.RECOVERY_LOCALIZED,
                "apply-exact-cut": RequestStage.CUT_APPLIED,
                "verify-replay": RequestStage.VERIFIED,
            }[action]
            case.event_log.append(self._event_for(action))
            return self.customer_snapshot(customer_id)

    def _customer(self, customer_id: str) -> SyntheticCustomer:
        try:
            return self._customer_by_id[customer_id]
        except KeyError as error:
            raise ValueError(f"unknown synthetic customer: {customer_id}") from error

    def _customer_summary(self, customer: SyntheticCustomer) -> dict[str, Any]:
        stage = self._cases[customer.customer_id].stage
        return {
            "customer_id": customer.customer_id,
            "display_name": customer.display_name,
            "account_alias": customer.account_alias,
            "risk_tier": customer.risk_tier,
            "is_demo_subject": customer.is_demo_subject,
            "stage": stage.value,
            "artifact_count": len(ARTIFACTS),
        }

    @staticmethod
    def _verdict(stage: RequestStage) -> dict[str, str]:
        if stage is RequestStage.NO_REQUEST:
            return {"status": "NOT_REQUESTED", "reason": "No deletion request exists for this synthetic customer."}
        if stage is RequestStage.REQUESTED:
            return {"status": "INCOMPLETE", "reason": "Registered subject artifacts are still active."}
        if stage is RequestStage.VISIBLE_COPIES_ERASED:
            return {"status": "UNVERIFIED", "reason": "Visible copies are absent, but future recovery and model evidence remain open."}
        if stage is RequestStage.RECURRENCE_OBSERVED:
            return {"status": "INCOMPLETE", "reason": "A scheduled backup restore recreated a reachable face template."}
        if stage is RequestStage.RECOVERY_LOCALIZED:
            return {"status": "INCOMPLETE", "reason": "Backup restore is localized; exact remediation has not been replayed."}
        if stage is RequestStage.CUT_APPLIED:
            return {"status": "UNVERIFIED", "reason": "Actions are recorded, but the mandatory replay check has not completed."}
        return {"status": "COMPLETE", "reason": "All registered synthetic artifacts passed replay verification in this declared topology."}

    @staticmethod
    def _artifacts(stage: RequestStage) -> list[dict[str, str]]:
        if stage in {RequestStage.NO_REQUEST, RequestStage.REQUESTED}:
            states = ("ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE")
        elif stage is RequestStage.VISIBLE_COPIES_ERASED:
            states = ("ERASED", "ERASED", "ERASED", "ERASED", "LATENT", "UNVERIFIED")
        elif stage in {RequestStage.RECURRENCE_OBSERVED, RequestStage.RECOVERY_LOCALIZED}:
            states = ("ERASED", "ERASED", "ERASED", "ACTIVE", "ACTIVE", "UNVERIFIED")
        else:
            states = ("ERASED", "ERASED", "ERASED", "ERASED", "ERASED", "ERASED")
        return [
            {"connector_id": connector_id, "id": artifact_id, "label": label, "kind": kind, "state": state}
            for (connector_id, artifact_id, label, kind), state in zip(ARTIFACTS, states, strict=True)
        ]

    @staticmethod
    def _dry_run(stage: RequestStage) -> list[dict[str, str]]:
        if stage in {RequestStage.NO_REQUEST, RequestStage.REQUESTED}:
            return [
                {"connector": "postgres", "action": "delete subject KYC profile", "status": "PLANNED"},
                {"connector": "keycloak", "action": "revoke subject sessions", "status": "PLANNED"},
                {"connector": "redis", "action": "invalidate subject cache", "status": "PLANNED"},
                {"connector": "qdrant", "action": "delete face vector", "status": "PLANNED"},
                {"connector": "minio", "action": "inspect recovery manifest", "status": "PLANNED"},
            ]
        if stage in {RequestStage.RECURRENCE_OBSERVED, RequestStage.RECOVERY_LOCALIZED}:
            return [
                {"connector": "minio", "action": "exclude subject snapshot and block restore", "status": "REQUIRED"},
                {"connector": "qdrant", "action": "delete restored face template", "status": "REQUIRED"},
                {"connector": "keycloak", "action": "invalidate rehydrated identity session", "status": "REQUIRED"},
                {"connector": "model", "action": "require exact-retraining evidence", "status": "REQUIRED"},
            ]
        if stage is RequestStage.CUT_APPLIED:
            return [{"connector": "erasemap", "action": "replay every registered channel", "status": "REQUIRED"}]
        return []

    @staticmethod
    def _event_for(action: str) -> str:
        return {
            "create-request": "Deletion request created with approval-required policy.",
            "delete-visible": "PostgreSQL, Keycloak, Redis and Qdrant visible artifacts marked erased.",
            "simulate-recovery": "MinIO scheduled restore recreated the Qdrant face template.",
            "run-probes": "Three bounded probes localized the declared backup-restore mechanism.",
            "apply-exact-cut": "Restore job blocked; subject snapshot, vector and sessions invalidated.",
            "verify-replay": "All six registered channels replayed; synthetic certificate issued.",
        }[action]
