from src.core.enums import MappingMethod, StandardMetric
from src.mapping.service import SemanticMapper


class TestSemanticMapper:
    def test_exact_synonym(self, db_session):
        mapper = SemanticMapper(db_session)
        result = mapper.map_label("Net Sales")
        assert result.metric == StandardMetric.REVENUE
        assert result.mapping_score >= 0.9
        assert result.method == MappingMethod.RULE_BASED

    def test_ebitda_mapping(self, db_session):
        mapper = SemanticMapper(db_session)
        result = mapper.map_label("EBITDA")
        assert result.metric == StandardMetric.EBITDA

    def test_partial_match(self, db_session):
        mapper = SemanticMapper(db_session)
        result = mapper.map_label("Total Revenue for Q2")
        assert result.metric == StandardMetric.REVENUE
        assert result.mapping_score > 0.0

    def test_no_match(self, db_session):
        mapper = SemanticMapper(db_session)
        result = mapper.map_label("Random Gibberish Label XYZ")
        assert result.metric is None
        assert result.mapping_score == 0.0

    def test_company_approved_mapping(self, db_session):
        mapper = SemanticMapper(db_session)
        mapper.add_company_mapping("ACME", "Umsatz", StandardMetric.REVENUE)
        result = mapper.map_label("Umsatz", company_id="ACME")
        assert result.metric == StandardMetric.REVENUE
        assert result.mapping_score >= 0.95  # scales with approval count
        assert result.method == MappingMethod.COMPANY_APPROVED

    def test_company_mapping_priority(self, db_session):
        mapper = SemanticMapper(db_session)
        mapper.add_company_mapping("ACME", "Net Sales", StandardMetric.NET_INCOME)
        result = mapper.map_label("Net Sales", company_id="ACME")
        assert result.metric == StandardMetric.NET_INCOME

    def test_case_insensitive(self, db_session):
        mapper = SemanticMapper(db_session)
        result = mapper.map_label("REVENUE")
        assert result.metric == StandardMetric.REVENUE

    def test_balance_sheet_items(self, db_session):
        mapper = SemanticMapper(db_session)
        assert mapper.map_label("Total Assets").metric == StandardMetric.ASSETS
        assert mapper.map_label("Total Liabilities").metric == StandardMetric.LIABILITIES
        assert mapper.map_label("Total Equity").metric == StandardMetric.EQUITY

    def test_company_mapping_persisted(self, db_session):
        """Verify company mappings survive across mapper instances."""
        mapper1 = SemanticMapper(db_session)
        mapper1.add_company_mapping("ACME", "Umsatz", StandardMetric.REVENUE)

        mapper2 = SemanticMapper(db_session)
        result = mapper2.map_label("Umsatz", company_id="ACME")
        assert result.metric == StandardMetric.REVENUE
        assert result.method == MappingMethod.COMPANY_APPROVED
