"""
Tests unitaires pour utils/validators.py
"""
import pytest

from utils import validators


class TestEnvBool:
    """Tests pour env_bool()"""
    
    @pytest.mark.unit
    def test_env_bool_true_lowercase(self):
        """Test conversion de 'true' en booléen"""
        result = validators.env_bool("true")
        assert result is True
    
    @pytest.mark.unit
    def test_env_bool_true_uppercase(self):
        """Test conversion de 'TRUE' en booléen"""
        result = validators.env_bool("TRUE")
        assert result is True
    
    @pytest.mark.unit
    def test_env_bool_one(self):
        """Test conversion de '1' en True"""
        result = validators.env_bool("1")
        assert result is True
    
    @pytest.mark.unit
    def test_env_bool_yes(self):
        """Test conversion de 'yes' en True"""
        result = validators.env_bool("yes")
        assert result is True
    
    @pytest.mark.unit
    def test_env_bool_false_lowercase(self):
        """Test conversion de 'false' en booléen"""
        result = validators.env_bool("false")
        assert result is False
    
    @pytest.mark.unit
    def test_env_bool_false_uppercase(self):
        """Test conversion de 'FALSE' en booléen"""
        result = validators.env_bool("FALSE")
        assert result is False
    
    @pytest.mark.unit
    def test_env_bool_zero(self):
        """Test conversion de '0' en False"""
        result = validators.env_bool("0")
        assert result is False
    
    @pytest.mark.unit
    def test_env_bool_no(self):
        """Test conversion de 'no' en False"""
        result = validators.env_bool("no")
        assert result is False
    
    @pytest.mark.unit
    def test_env_bool_empty_string(self):
        """Test conversion de chaîne vide (défaut False)"""
        result = validators.env_bool("")
        assert result is False
    
    @pytest.mark.unit
    def test_env_bool_none(self):
        """Test conversion de None (défaut False)"""
        result = validators.env_bool(None)
        assert result is False
    
    @pytest.mark.unit
    def test_env_bool_custom_default(self):
        """Test conversion avec défaut personnalisé"""
        result = validators.env_bool("", default=True)
        assert result is True
    
    @pytest.mark.unit
    def test_env_bool_invalid_value(self):
        """Test conversion d'une valeur invalide (retourne défaut)"""
        result = validators.env_bool("maybe")
        assert result is False


class TestNormalizeMakeWebhookUrl:
    """Tests pour normalize_make_webhook_url()"""
    
    @pytest.mark.unit
    def test_normalize_full_https_url(self):
        """Test normalisation d'une URL HTTPS complète"""
        result = validators.normalize_make_webhook_url("https://hook.eu2.make.com/abc123")
        assert result == "https://hook.eu2.make.com/abc123"
    
    @pytest.mark.unit
    def test_normalize_http_url(self):
        """Test normalisation d'une URL HTTP (acceptée telle quelle)"""
        result = validators.normalize_make_webhook_url("http://hook.eu2.make.com/abc123")
        assert result == "http://hook.eu2.make.com/abc123"
    
    @pytest.mark.unit
    def test_normalize_alias_format(self):
        """Test normalisation du format alias token@hook.eu2.make.com"""
        result = validators.normalize_make_webhook_url("abc123@hook.eu2.make.com")
        assert result == "https://hook.eu2.make.com/abc123"
    
    @pytest.mark.unit
    def test_normalize_token_only(self):
        """Test normalisation d'un token seul"""
        result = validators.normalize_make_webhook_url("abc123xyz")
        assert result == "https://hook.eu2.make.com/abc123xyz"
    
    @pytest.mark.unit
    def test_normalize_none(self):
        """Test normalisation de None"""
        result = validators.normalize_make_webhook_url(None)
        assert result is None
    
    @pytest.mark.unit
    def test_normalize_empty_string(self):
        """Test normalisation d'une chaîne vide"""
        result = validators.normalize_make_webhook_url("")
        assert result is None
    
    @pytest.mark.unit
    def test_normalize_whitespace_only(self):
        """Test normalisation d'espaces uniquement"""
        result = validators.normalize_make_webhook_url("   ")
        assert result is None
    
    @pytest.mark.unit
    def test_normalize_preserves_path(self):
        """Test que le chemin est préservé"""
        result = validators.normalize_make_webhook_url("https://hook.eu2.make.com/abc123/extra/path")
        assert result == "https://hook.eu2.make.com/abc123/extra/path"
    
    @pytest.mark.unit
    def test_normalize_different_domain(self):
        """Test avec un domaine hook différent"""
        result = validators.normalize_make_webhook_url("https://hook.us1.make.com/xyz789")
        assert result == "https://hook.us1.make.com/xyz789"
