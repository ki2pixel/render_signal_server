"""
Tests unitaires pour utils/time_helpers.py
"""
import pytest
from datetime import time, datetime
from zoneinfo import ZoneInfo

from utils import time_helpers


class TestParseTimeHHMM:
    """Tests pour parse_time_hhmm()"""
    
    @pytest.mark.unit
    def test_parse_valid_time_hhmm(self):
        """Test parsing d'un temps valide au format HH:MM"""
        result = time_helpers.parse_time_hhmm("14:30")
        assert result == time(14, 30)
    
    @pytest.mark.unit
    def test_parse_valid_time_with_colon(self):
        """Test parsing d'un temps valide au format HH:MM"""
        result = time_helpers.parse_time_hhmm("09:45")
        assert result == time(9, 45)
    
    @pytest.mark.unit
    def test_parse_single_digit_hour(self):
        """Test parsing d'une heure à un chiffre"""
        result = time_helpers.parse_time_hhmm("9:05")
        assert result == time(9, 5)
    
    @pytest.mark.unit
    def test_parse_midnight(self):
        """Test parsing de minuit"""
        result = time_helpers.parse_time_hhmm("00:00")
        assert result == time(0, 0)
    
    @pytest.mark.unit
    def test_parse_invalid_format(self):
        """Test parsing d'un format invalide"""
        result = time_helpers.parse_time_hhmm("invalid")
        assert result is None
    
    @pytest.mark.unit
    def test_parse_empty_string(self):
        """Test parsing d'une chaîne vide"""
        result = time_helpers.parse_time_hhmm("")
        assert result is None
    
    @pytest.mark.unit
    def test_parse_none(self):
        """Test parsing de None"""
        result = time_helpers.parse_time_hhmm(None)
        assert result is None
    
    @pytest.mark.unit
    def test_parse_invalid_hour(self):
        """Test parsing d'une heure invalide (> 23)"""
        result = time_helpers.parse_time_hhmm("25:00")
        assert result is None
    
    @pytest.mark.unit
    def test_parse_invalid_minute(self):
        """Test parsing de minutes invalides (> 59)"""
        result = time_helpers.parse_time_hhmm("14:65")
        assert result is None


class TestIsWithinTimeWindowLocal:
    """Tests pour is_within_time_window_local()"""
    
    @pytest.mark.unit
    def test_within_window_same_day(self):
        """Test qu'un temps est dans la fenêtre le même jour"""
        tz = ZoneInfo("Europe/Paris")
        start = time(9, 0)
        end = time(17, 0)
        
        # 14:00 est dans la fenêtre 9:00-17:00
        now = datetime(2025, 10, 13, 14, 0, 0, tzinfo=tz)
        result = time_helpers.is_within_time_window_local(now, start, end)
        assert result is True
    
    @pytest.mark.unit
    def test_outside_window_before(self):
        """Test qu'un temps avant la fenêtre est exclu"""
        tz = ZoneInfo("Europe/Paris")
        start = time(9, 0)
        end = time(17, 0)
        
        # 8:00 est avant la fenêtre 9:00-17:00
        now = datetime(2025, 10, 13, 8, 0, 0, tzinfo=tz)
        result = time_helpers.is_within_time_window_local(now, start, end)
        assert result is False
    
    @pytest.mark.unit
    def test_outside_window_after(self):
        """Test qu'un temps après la fenêtre est exclu"""
        tz = ZoneInfo("Europe/Paris")
        start = time(9, 0)
        end = time(17, 0)
        
        # 18:00 est après la fenêtre 9:00-17:00
        now = datetime(2025, 10, 13, 18, 0, 0, tzinfo=tz)
        result = time_helpers.is_within_time_window_local(now, start, end)
        assert result is False
    
    @pytest.mark.unit
    def test_at_start_boundary(self):
        """Test qu'un temps exactement au début est inclus"""
        tz = ZoneInfo("Europe/Paris")
        start = time(9, 0)
        end = time(17, 0)
        
        # 9:00 exactement
        now = datetime(2025, 10, 13, 9, 0, 0, tzinfo=tz)
        result = time_helpers.is_within_time_window_local(now, start, end)
        assert result is True
    
    @pytest.mark.unit
    def test_at_end_boundary(self):
        """Test qu'un temps exactement à la fin est exclu"""
        tz = ZoneInfo("Europe/Paris")
        start = time(9, 0)
        end = time(17, 0)
        
        # 17:00 exactement
        now = datetime(2025, 10, 13, 17, 0, 0, tzinfo=tz)
        result = time_helpers.is_within_time_window_local(now, start, end)
        assert result is False
    
    @pytest.mark.unit
    def test_overnight_window_before_midnight(self):
        """Test fenêtre de nuit (ex: 22:00-06:00) avant minuit"""
        tz = ZoneInfo("Europe/Paris")
        start = time(22, 0)
        end = time(6, 0)
        
        # 23:00 est dans la fenêtre 22:00-06:00
        now = datetime(2025, 10, 13, 23, 0, 0, tzinfo=tz)
        result = time_helpers.is_within_time_window_local(now, start, end)
        assert result is True
    
    @pytest.mark.unit
    def test_overnight_window_after_midnight(self):
        """Test fenêtre de nuit (ex: 22:00-06:00) après minuit"""
        tz = ZoneInfo("Europe/Paris")
        start = time(22, 0)
        end = time(6, 0)
        
        # 02:00 est dans la fenêtre 22:00-06:00
        now = datetime(2025, 10, 13, 2, 0, 0, tzinfo=tz)
        result = time_helpers.is_within_time_window_local(now, start, end)
        assert result is True
    
    @pytest.mark.unit
    def test_overnight_window_outside(self):
        """Test fenêtre de nuit (ex: 22:00-06:00) en dehors"""
        tz = ZoneInfo("Europe/Paris")
        start = time(22, 0)
        end = time(6, 0)
        
        # 12:00 n'est pas dans la fenêtre 22:00-06:00
        now = datetime(2025, 10, 13, 12, 0, 0, tzinfo=tz)
        result = time_helpers.is_within_time_window_local(now, start, end)
        assert result is False
