import unittest

from greeting import greet


class GreetTests(unittest.TestCase):
    def test_greets_ada(self):
        self.assertEqual(greet("Ada"), "Hello, Ada!")


if __name__ == "__main__":
    unittest.main()
