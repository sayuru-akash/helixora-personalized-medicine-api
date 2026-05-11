from django.test import TestCase
from django.urls import reverse


class LandingPageTests(TestCase):
	def test_landing_page_renders(self):
		response = self.client.get(reverse('landing-page'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Helixora AI')
		self.assertContains(response, 'Build, review, and trace recommendation workflows.')