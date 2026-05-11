from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.ai.providers import PlaceholderRecommendationProvider, get_provider_status, get_recommendation_provider


class AIProviderSelectionTests(SimpleTestCase):
	def test_placeholder_provider_is_default(self):
		with patch.dict('os.environ', {}, clear=False):
			provider = get_recommendation_provider()

		self.assertIsInstance(provider, PlaceholderRecommendationProvider)

	def test_gemini_without_key_falls_back_to_placeholder(self):
		with patch.dict('os.environ', {'HELIXORA_AI_PROVIDER': 'gemini', 'GEMINI_API_KEY': ''}, clear=False):
			provider = get_recommendation_provider()

		self.assertIsInstance(provider, PlaceholderRecommendationProvider)

	def test_provider_status_reports_fallback(self):
		with patch.dict('os.environ', {'HELIXORA_AI_PROVIDER': 'gemini', 'GEMINI_API_KEY': ''}, clear=False):
			status = get_provider_status()

		self.assertEqual(status['configured_provider'], 'gemini')
		self.assertEqual(status['active_provider'], 'placeholder')
		self.assertFalse(status['gemini_api_key_present'])