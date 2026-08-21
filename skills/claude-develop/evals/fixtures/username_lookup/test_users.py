import unittest

from service import get_user


class GetUserTests(unittest.TestCase):
    def test_lowercase_username_returns_alice(self):
        self.assertEqual(get_user("alice"), {"username": "Alice"})

    def test_uppercase_username_returns_alice(self):
        self.assertEqual(get_user("ALICE"), {"username": "Alice"})


if __name__ == "__main__":
    unittest.main()
