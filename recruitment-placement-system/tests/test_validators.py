import unittest
from datetime import date
from decimal import Decimal

from app.exceptions import ValidationError
from app.validation import validators as v


class ValidatorTests(unittest.TestCase):
    def assertRaisesMessage(self, message, func, *args):
        with self.assertRaises(ValidationError) as ctx:
            func(*args)
        self.assertEqual(str(ctx.exception), message)

    def test_email(self):
        self.assertEqual(v.validate_email(" Rahul@Example.COM "), "rahul@example.com")
        self.assertRaisesMessage("Enter a valid email address.", v.validate_email, "not-an-email")

    def test_mobile_requires_ten_digits(self):
        self.assertEqual(v.validate_mobile("98765 43210"), "9876543210")
        self.assertRaisesMessage("Mobile number must contain 10 digits.", v.validate_mobile, "12345")

    def test_percentage_range(self):
        self.assertEqual(v.validate_percentage("68.5"), Decimal("68.5"))
        self.assertIsNone(v.validate_percentage(""))
        self.assertRaisesMessage("Percentage must be between 0 and 100.", v.validate_percentage, "101")

    def test_openings_must_be_positive(self):
        self.assertRaisesMessage("Number of openings must be greater than zero.", v.validate_openings, "0")
        self.assertEqual(v.validate_openings("15"), 15)

    def test_deadline_not_before_posted_date(self):
        self.assertRaisesMessage("Application deadline cannot be before posted date.",
                                 v.validate_deadline, date(2026, 10, 5), date(2026, 10, 1))

    def test_package_range(self):
        self.assertRaisesMessage("Minimum package cannot exceed maximum package.",
                                 v.validate_package_range, Decimal("6"), Decimal("5"))

    def test_interview_date_not_in_past(self):
        self.assertRaisesMessage("Interview date cannot be in the past.",
                                 v.validate_interview_date, date(2026, 10, 1), date(2026, 10, 30))
        self.assertEqual(v.validate_interview_date(date(2026, 11, 3), date(2026, 10, 30)), date(2026, 11, 3))

    def test_backlog_cannot_be_negative(self):
        self.assertRaisesMessage("Backlog count cannot be negative.", v.validate_backlog_count, "-1")
        self.assertEqual(v.validate_backlog_count(""), 0)

    def test_candidate_name_required(self):
        self.assertRaisesMessage("Please enter candidate name.", v.require_text, "   ", "Please enter candidate name.")

    def test_parse_date_and_time(self):
        self.assertEqual(v.parse_date("2026-11-03", "Date"), date(2026, 11, 3))
        self.assertRaises(ValidationError, v.parse_date, "03/11/2026", "Date")
        self.assertEqual(v.parse_time("11:30"), "11:30:00")
        self.assertIsNone(v.parse_time(""))
        self.assertRaises(ValidationError, v.parse_time, "25:00")

    def test_passing_year_window(self):
        self.assertRaisesMessage("Passing year must be between 1990 and 2035.",
                                 v.parse_int, "1980", "Passing year", True, 1990, 2035)
        self.assertRaisesMessage("Minimum passing year cannot exceed maximum passing year.",
                                 v.validate_year_window, 2026, 2024)

    def test_choice_is_case_insensitive_and_strict(self):
        self.assertEqual(v.choice("open", ("OPEN", "CLOSED"), "Status"), "OPEN")
        self.assertRaises(ValidationError, v.choice, "PAUSED", ("OPEN", "CLOSED"), "Status")

    def test_rating_bounds(self):
        self.assertEqual(v.validate_rating("4.5", "Technical"), Decimal("4.5"))
        self.assertRaises(ValidationError, v.validate_rating, "6", "Technical")


if __name__ == "__main__":
    unittest.main()
