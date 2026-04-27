"""Tests for categorize_listing() in scrape_listings.py."""
import pytest
from scrape_listings import categorize_listing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def has(categories, category):
    return category in categories

def only(categories, category):
    return categories == [category]


# ---------------------------------------------------------------------------
# Age Verified — should be tagged
# ---------------------------------------------------------------------------

class TestAgeVerifiedPositives:
    def test_age_verified_explicit(self):
        assert has(categorize_listing("Roblox Account | Age Verified | Voice Chat", "Roblox"), "Age Verified")

    def test_age_verification_noun(self):
        assert has(categorize_listing("Roblox acc with age verification + full access", "Roblox"), "Age Verified")

    def test_verified_age(self):
        assert has(categorize_listing("Verified Age Roblox account for sale", "Roblox"), "Age Verified")

    def test_voice_chat(self):
        assert has(categorize_listing("Roblox account voice chat enabled", "Roblox"), "Age Verified")

    def test_voice_enabled(self):
        assert has(categorize_listing("Roblox acc | voice enabled | OG 2012", "Roblox"), "Age Verified")

    def test_voice_verified(self):
        assert has(categorize_listing("Voice Verified Roblox Account", "Roblox"), "Age Verified")

    def test_vc_enabled(self):
        assert has(categorize_listing("Roblox account vc enabled + stacked", "Roblox"), "Age Verified")

    def test_vc_account(self):
        assert has(categorize_listing("OG VC Account Roblox 2010", "Roblox"), "Age Verified")

    def test_with_vc(self):
        assert has(categorize_listing("Roblox acc with vc | full access", "Roblox"), "Age Verified")

    def test_has_vc(self):
        assert has(categorize_listing("Roblox account has vc rare username", "Roblox"), "Age Verified")

    def test_18plus(self):
        assert has(categorize_listing("18+ Roblox Account Age Verified", "Roblox"), "Age Verified")

    def test_18_years(self):
        assert has(categorize_listing("Roblox account 18 years old verified", "Roblox"), "Age Verified")

    def test_over_18(self):
        assert has(categorize_listing("Roblox over 18 verified account", "Roblox"), "Age Verified")

    def test_13plus(self):
        assert has(categorize_listing("Roblox 13+ voice chat account", "Roblox"), "Age Verified")

    def test_over_13(self):
        assert has(categorize_listing("Roblox over 13 account vc enabled", "Roblox"), "Age Verified")

    def test_id_verified(self):
        assert has(categorize_listing("ID Verified Roblox Account Full Access", "Roblox"), "Age Verified")

    def test_id_verification(self):
        assert has(categorize_listing("Roblox acc id verification done + email", "Roblox"), "Age Verified")

    def test_gov_id(self):
        assert has(categorize_listing("Roblox account gov id verified voice chat", "Roblox"), "Age Verified")

    def test_government_id(self):
        assert has(categorize_listing("Roblox government id verified account", "Roblox"), "Age Verified")

    def test_passport_verified(self):
        assert has(categorize_listing("Roblox account passport verified age", "Roblox"), "Age Verified")

    def test_phone_verified(self):
        assert has(categorize_listing("Phone Verified Roblox Account | VC", "Roblox"), "Age Verified")

    def test_adult_verified(self):
        assert has(categorize_listing("Adult Verified Roblox Account for sale", "Roblox"), "Age Verified")

    def test_age_gate(self):
        assert has(categorize_listing("Roblox account age gate passed full access", "Roblox"), "Age Verified")

    def test_age_check(self):
        assert has(categorize_listing("Roblox acc age check cleared voice enabled", "Roblox"), "Age Verified")

    def test_case_insensitive(self):
        assert has(categorize_listing("ROBLOX ACCOUNT AGE VERIFIED VOICE CHAT", "Roblox"), "Age Verified")


# ---------------------------------------------------------------------------
# Age Verified — should NOT be tagged (disqualifiers + irrelevant matches)
# ---------------------------------------------------------------------------

class TestAgeVerifiedNegatives:
    def test_email_verification_disqualified(self):
        assert not has(categorize_listing("Roblox account with email verification included", "Roblox"), "Age Verified")

    def test_payment_verification_disqualified(self):
        assert not has(categorize_listing("Roblox acc payment verification required", "Roblox"), "Age Verified")

    def test_verification_service_disqualified(self):
        assert not has(categorize_listing("Roblox verification service account setup", "Roblox"), "Age Verified")

    def test_passport_to_disqualified(self):
        assert not has(categorize_listing("Roblox account passport to adventure item", "Roblox"), "Age Verified")

    def test_plain_verification_no_tag(self):
        # "verification" alone no longer triggers — removed from keyword list
        assert not has(categorize_listing("Roblox account verification badge", "Roblox"), "Age Verified")

    def test_plain_passport_no_tag(self):
        # "passport" alone no longer triggers — removed from keyword list
        assert not has(categorize_listing("Roblox passport collector account", "Roblox"), "Age Verified")

    def test_generic_account_no_tag(self):
        assert not has(categorize_listing("Cheap Roblox account for sale", "Roblox"), "Age Verified")

    def test_items_no_tag(self):
        assert not has(categorize_listing("Roblox robux 10000 donation", "Roblox"), "Age Verified")


# ---------------------------------------------------------------------------
# Multi-category listings (Age Verified + OG, etc.)
# ---------------------------------------------------------------------------

class TestAgeVerifiedMultiCategory:
    def test_age_verified_and_og(self):
        cats = categorize_listing("OG 2009 Roblox Account | Age Verified | Voice Chat", "Roblox")
        assert has(cats, "Age Verified")
        assert has(cats, "OG / Veteran Account")

    def test_age_verified_not_general(self):
        cats = categorize_listing("Roblox Account | Age Verified", "Roblox")
        assert has(cats, "Age Verified")
        assert "General" not in cats

    def test_unrelated_title_is_general(self):
        assert only(categorize_listing("Roblox account cheap fast delivery", "Roblox"), "General")


# ---------------------------------------------------------------------------
# Other categories — make sure age-verified changes didn't break them
# ---------------------------------------------------------------------------

class TestOtherCategoriesUnaffected:
    def test_items_currency(self):
        assert has(categorize_listing("10000 Robux donation pls donate", "Roblox"), "Items / Currency")

    def test_og_veteran(self):
        assert has(categorize_listing("2008 OG Roblox account rare username", "Roblox"), "OG / Veteran Account")

    def test_og_4letter(self):
        assert has(categorize_listing("4 letter Roblox username account", "Roblox"), "OG / Veteran Account")

    def test_general_fallback(self):
        assert only(categorize_listing("Roblox account full access instant delivery", "Roblox"), "General")
