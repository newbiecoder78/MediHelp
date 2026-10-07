"""
tests/test_brand_mapper.py

Unit tests for the brand mapper service.
Run with: python -m pytest tests/test_brand_mapper.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.brand_mapper import map_brand_to_generic, resolve_drug_names, split_combo_drug


class TestMapBrandToGeneric:

    def test_exact_match_crocin(self):
        generic, mapped = map_brand_to_generic("Crocin")
        assert generic == "paracetamol"
        assert mapped is True

    def test_exact_match_dolo(self):
        generic, mapped = map_brand_to_generic("Dolo")
        assert generic == "paracetamol"
        assert mapped is True

    def test_exact_match_combiflam(self):
        generic, mapped = map_brand_to_generic("Combiflam")
        assert generic == "ibuprofen+paracetamol"
        assert mapped is True

    def test_exact_match_ecosprin(self):
        generic, mapped = map_brand_to_generic("Ecosprin")
        assert generic == "aspirin"
        assert mapped is True

    def test_case_insensitive(self):
        generic1, _ = map_brand_to_generic("CROCIN")
        generic2, _ = map_brand_to_generic("crocin")
        generic3, _ = map_brand_to_generic("Crocin")
        assert generic1 == generic2 == generic3 == "paracetamol"

    def test_unknown_brand_returns_original(self):
        generic, mapped = map_brand_to_generic("SomeUnknownBrand99")
        assert generic == "someunknownbrand99"
        assert mapped is False

    def test_generic_name_passthrough(self):
        # "warfarin" is already a generic name — should pass through
        generic, mapped = map_brand_to_generic("warfarin")
        assert mapped is False
        assert generic == "warfarin"

    def test_fuzzy_match_typo(self):
        # "Ecospring" is close enough to "ecosprin" to fuzzy match
        generic, mapped = map_brand_to_generic("Ecospring")
        assert mapped is True
        assert generic == "aspirin"


class TestSplitComboDrug:

    def test_non_combo_returns_list_of_one(self):
        parts = split_combo_drug("paracetamol")
        assert parts == ["paracetamol"]

    def test_combo_splits_correctly(self):
        parts = split_combo_drug("ibuprofen+paracetamol")
        assert parts == ["ibuprofen", "paracetamol"]

    def test_combo_with_spaces(self):
        parts = split_combo_drug("amoxicillin + clavulanic acid")
        assert parts == ["amoxicillin", "clavulanic acid"]


class TestResolveDrugNames:

    def test_resolves_brand_names(self):
        results = resolve_drug_names(["Crocin", "Ecosprin"])
        assert len(results) == 2
        generics = [r["generic"] for r in results]
        assert "paracetamol" in generics
        assert "aspirin" in generics

    def test_combo_drug_splits_into_two(self):
        results = resolve_drug_names(["Combiflam"])
        assert len(results) == 2
        generics = [r["generic"] for r in results]
        assert "ibuprofen" in generics
        assert "paracetamol" in generics

    def test_empty_input(self):
        results = resolve_drug_names([])
        assert results == []

    def test_skips_empty_strings(self):
        results = resolve_drug_names(["", "  ", "Crocin"])
        assert len(results) == 1
