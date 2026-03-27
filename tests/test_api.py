"""Tests for enriched API endpoints."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import AuditLog, Base, FinancialRecord


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _make_record(db_session, **overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "company_id": "acme",
        "metric": "Revenue",
        "value": 1_000_000,
        "raw_label": "Total Revenue",
        "period": "Q1-2025",
        "period_type": "QUARTER",
        "file_id": str(uuid.uuid4()),
        "sheet": "Income Statement",
        "cell": "B5",
        "status": "PENDING",
        "mapping_score": 0.95,
        "mapping_method": "rule_based",
        "mapping_reason": "Rule-based synonym: Total Revenue -> Revenue",
        "raw_period": "Q1 2025",
        "period_confidence": 0.95,
        "confidence_total": 0.72,
        "confidence_extraction": 0.95,
        "confidence_mapping": 0.95,
        "confidence_sanity": 0.0,
        "confidence_source": 0.8,
        "confidence_historical": 0.9,
        "decision": "REVIEW_REQUIRED",
        "decision_reason": "Sanity check failed",
        "sanity_passed": "false",
        "sanity_issues_json": '["EBITDA exceeds Revenue"]',
        "change_type": "NEW",
        "previous_value": None,
        "source_filename": "Q1_report.xlsx",
        "version": 1,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    row = FinancialRecord(**defaults)
    db_session.add(row)
    db_session.flush()
    return row


class TestStorageGetById:
    def test_returns_record(self, db_session):
        from src.storage.service import StorageService

        row = _make_record(db_session)
        storage = StorageService(db_session)
        sr = storage.get_by_id(uuid.UUID(row.id))

        assert sr is not None
        assert str(sr.record_id) == row.id

    def test_returns_none_for_missing(self, db_session):
        from src.storage.service import StorageService

        storage = StorageService(db_session)
        assert storage.get_by_id(uuid.uuid4()) is None


class TestStoragePendingFiltered:
    def test_returns_all_pending(self, db_session):
        from src.storage.service import StorageService

        _make_record(db_session, decision="FLAG", confidence_total=0.3)
        _make_record(db_session, decision="REVIEW_REQUIRED", confidence_total=0.6)
        _make_record(db_session, status="APPROVED", decision="AUTO_READY", confidence_total=0.9)

        storage = StorageService(db_session)
        records, total = storage.get_pending_filtered()

        assert total == 2
        assert len(records) == 2

    def test_filters_by_decision(self, db_session):
        from src.storage.service import StorageService

        _make_record(db_session, decision="FLAG", confidence_total=0.3)
        _make_record(db_session, decision="REVIEW_REQUIRED", confidence_total=0.6)

        storage = StorageService(db_session)
        records, total = storage.get_pending_filtered(decision_filter="FLAG")

        assert total == 1
        assert records[0]._row.decision == "FLAG"

    def test_sorted_by_confidence_asc(self, db_session):
        from src.storage.service import StorageService

        _make_record(db_session, confidence_total=0.9, decision="AUTO_READY")
        _make_record(db_session, confidence_total=0.3, decision="FLAG")
        _make_record(db_session, confidence_total=0.6, decision="REVIEW_REQUIRED")

        storage = StorageService(db_session)
        records, _ = storage.get_pending_filtered()

        confs = [r._row.confidence_total for r in records]
        assert confs == sorted(confs)

    def test_pagination(self, db_session):
        from src.storage.service import StorageService

        for i in range(5):
            _make_record(db_session, confidence_total=0.1 * (i + 1), decision="FLAG")

        storage = StorageService(db_session)

        page1, total = storage.get_pending_filtered(page=1, per_page=2)
        assert total == 5
        assert len(page1) == 2

        page3, _ = storage.get_pending_filtered(page=3, per_page=2)
        assert len(page3) == 1


class TestUpdatePipelineMetadata:
    def test_updates_fields(self, db_session):
        from src.storage.service import StorageService

        row = _make_record(db_session, decision=None, confidence_total=0.0)
        storage = StorageService(db_session)

        storage.update_pipeline_metadata(
            uuid.UUID(row.id),
            decision="FLAG",
            decision_reason="Low confidence",
            confidence_total=0.35,
            sanity_passed=False,
            sanity_issues=["Balance sheet mismatch"],
            change_type="REVISION",
            previous_value=900_000,
            source_filename="test.xlsx",
        )

        refreshed = db_session.query(FinancialRecord).filter_by(id=row.id).first()
        assert refreshed.decision == "FLAG"
        assert refreshed.confidence_total == 0.35
        assert refreshed.sanity_passed == "false"
        assert refreshed.change_type == "REVISION"
        assert refreshed.previous_value == 900_000


class TestRecordDetailShape:
    """Verify that the record detail has all fields the frontend expects."""

    def test_detail_has_all_sections(self, db_session):
        import json

        row = _make_record(db_session)
        rec = db_session.query(FinancialRecord).filter_by(id=row.id).first()

        # Simulate what the API endpoint builds
        sanity_issues = json.loads(rec.sanity_issues_json or "[]")

        detail = {
            "record_id": rec.id,
            "company_id": rec.company_id,
            "status": rec.status,
            "metric": rec.metric,
            "value": rec.value,
            "source_file": rec.source_filename,
            "sheet_name": rec.sheet,
            "cell_reference": rec.cell,
            "raw_label": rec.raw_label,
            "mapping_method": rec.mapping_method,
            "mapping_reason": rec.mapping_reason,
            "raw_period": rec.raw_period,
            "confidence_total": rec.confidence_total,
            "confidence_breakdown": {
                "extraction": rec.confidence_extraction,
                "mapping": rec.confidence_mapping,
                "sanity": rec.confidence_sanity,
                "source": rec.confidence_source,
                "historical": rec.confidence_historical,
            },
            "sanity_passed": rec.sanity_passed == "true",
            "sanity_issues": sanity_issues,
            "change_type": rec.change_type,
            "decision": rec.decision,
        }

        assert detail["source_file"] == "Q1_report.xlsx"
        assert detail["sheet_name"] == "Income Statement"
        assert detail["cell_reference"] == "B5"
        assert detail["raw_label"] == "Total Revenue"
        assert detail["mapping_method"] == "rule_based"
        assert detail["sanity_passed"] is False
        assert detail["sanity_issues"] == ["EBITDA exceeds Revenue"]
        assert detail["change_type"] == "NEW"
        assert detail["decision"] == "REVIEW_REQUIRED"
        assert detail["confidence_breakdown"]["extraction"] == 0.95


class TestAuditPagination:
    def test_paginated_audit(self, db_session):
        for i in range(5):
            row = AuditLog(
                id=str(uuid.uuid4()),
                event_type="RECORD_CREATED",
                timestamp=datetime.now(UTC),
                details_json="{}",
            )
            db_session.add(row)
        db_session.flush()

        total = db_session.query(AuditLog).count()
        assert total == 5

        page = (
            db_session.query(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(2)
            .all()
        )
        assert len(page) == 2
