"""
Tests unitaires pour utils/text_helpers.py
"""
import pytest

from utils import text_helpers


class TestNormalizeNoAccentsLowerTrim:
    """Tests pour normalize_no_accents_lower_trim()"""
    
    @pytest.mark.unit
    def test_normalize_simple_text(self):
        """Test normalisation d'un texte simple"""
        result = text_helpers.normalize_no_accents_lower_trim("Hello World")
        assert result == "hello world"
    
    @pytest.mark.unit
    def test_normalize_with_accents(self):
        """Test normalisation avec accents"""
        result = text_helpers.normalize_no_accents_lower_trim("Média Solutión")
        assert result == "media solution"
    
    @pytest.mark.unit
    def test_normalize_with_leading_trailing_spaces(self):
        """Test normalisation avec espaces avant/après"""
        result = text_helpers.normalize_no_accents_lower_trim("  test  ")
        assert result == "test"
    
    @pytest.mark.unit
    def test_normalize_empty_string(self):
        """Test normalisation d'une chaîne vide"""
        result = text_helpers.normalize_no_accents_lower_trim("")
        assert result == ""
    
    @pytest.mark.unit
    def test_normalize_none(self):
        """Test normalisation de None"""
        result = text_helpers.normalize_no_accents_lower_trim(None)
        assert result == ""
    
    @pytest.mark.unit
    def test_normalize_special_characters(self):
        """Test normalisation avec caractères spéciaux"""
        result = text_helpers.normalize_no_accents_lower_trim("Café-Bar!")
        assert result == "cafe-bar!"
    
    @pytest.mark.unit
    def test_normalize_multiple_spaces(self):
        """Test normalisation avec espaces multiples internes"""
        result = text_helpers.normalize_no_accents_lower_trim("Hello    World")
        assert "hello" in result and "world" in result


class TestStripLeadingReplyPrefixes:
    """Tests pour strip_leading_reply_prefixes()"""
    
    @pytest.mark.unit
    def test_strip_re_prefix(self):
        """Test suppression du préfixe Re:"""
        result = text_helpers.strip_leading_reply_prefixes("Re: Test Subject")
        assert result == "Test Subject"
    
    @pytest.mark.unit
    def test_strip_fw_prefix(self):
        """Test suppression du préfixe Fw:"""
        result = text_helpers.strip_leading_reply_prefixes("Fw: Test Subject")
        assert result == "Test Subject"
    
    @pytest.mark.unit
    def test_strip_fwd_prefix(self):
        """Test suppression du préfixe Fwd:"""
        result = text_helpers.strip_leading_reply_prefixes("Fwd: Test Subject")
        assert result == "Test Subject"
    
    @pytest.mark.unit
    def test_strip_tr_prefix_french(self):
        """Test suppression du préfixe TR: (français)"""
        result = text_helpers.strip_leading_reply_prefixes("TR: Test Subject")
        assert result == "Test Subject"
    
    @pytest.mark.unit
    def test_strip_multiple_prefixes(self):
        """Test suppression de préfixes multiples"""
        result = text_helpers.strip_leading_reply_prefixes("Re: Fw: Re: Test Subject")
        assert result == "Test Subject"
    
    @pytest.mark.unit
    def test_strip_case_insensitive(self):
        """Test suppression insensible à la casse"""
        result = text_helpers.strip_leading_reply_prefixes("re: FW: Test Subject")
        assert result == "Test Subject"
    
    @pytest.mark.unit
    def test_no_prefix(self):
        """Test sans préfixe"""
        result = text_helpers.strip_leading_reply_prefixes("Test Subject")
        assert result == "Test Subject"
    
    @pytest.mark.unit
    def test_empty_string(self):
        """Test avec chaîne vide"""
        result = text_helpers.strip_leading_reply_prefixes("")
        assert result == ""
    
    @pytest.mark.unit
    def test_none_input(self):
        """Test avec None en entrée"""
        result = text_helpers.strip_leading_reply_prefixes(None)
        assert result == ""


class TestDetectProvider:
    """Tests pour detect_provider()"""
    
    @pytest.mark.unit
    def test_detect_dropbox(self):
        """Test détection Dropbox"""
        url = "https://www.dropbox.com/scl/fo/abc123"
        result = text_helpers.detect_provider(url)
        assert result == "dropbox"
    
    @pytest.mark.unit
    def test_detect_fromsmash(self):
        """Test détection FromSmash"""
        url = "https://fromsmash.com/ABC-XYZ"
        result = text_helpers.detect_provider(url)
        assert result == "fromsmash"
    
    @pytest.mark.unit
    def test_detect_swisstransfer(self):
        """Test détection SwissTransfer"""
        url = "https://www.swisstransfer.com/d/uuid-here"
        result = text_helpers.detect_provider(url)
        assert result == "swisstransfer"
    
    @pytest.mark.unit
    def test_detect_unknown_provider(self):
        """Test détection d'un fournisseur inconnu"""
        url = "https://google.com/file"
        result = text_helpers.detect_provider(url)
        assert result == "unknown"
    
    @pytest.mark.unit
    def test_detect_case_insensitive(self):
        """Test détection insensible à la casse"""
        url = "HTTPS://WWW.DROPBOX.COM/scl/fo/abc123"
        result = text_helpers.detect_provider(url)
        assert result == "dropbox"
    
    @pytest.mark.unit
    def test_detect_empty_url(self):
        """Test avec URL vide"""
        result = text_helpers.detect_provider("")
        assert result == "unknown"
    
    @pytest.mark.unit
    def test_detect_none_url(self):
        """Test avec URL None"""
        result = text_helpers.detect_provider(None)
        assert result == "unknown"
