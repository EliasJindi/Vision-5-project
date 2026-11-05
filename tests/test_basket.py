import unittest

from voice_guidance import Basket, BasketResult

from tests.helpers import EAN_A, EAN_B


class BasketTest(unittest.TestCase):
    def test_a_product_is_added_once(self):
        basket = Basket()
        self.assertIs(basket.add(EAN_A, "Tomatpure"), BasketResult.ADDED)
        self.assertIs(basket.add(EAN_A, "Tomatpure"), BasketResult.ALREADY)
        self.assertEqual(len(basket), 1)
        self.assertIn(EAN_A, basket)

    def test_items_keep_the_order_they_were_added_in(self):
        basket = Basket()
        basket.add(EAN_B, "Kaffefilter")
        basket.add(EAN_A, "Tomatpure")
        self.assertEqual(basket.items(), [(EAN_B, "Kaffefilter"), (EAN_A, "Tomatpure")])
        self.assertEqual(basket.summary(), "Korgen (2): Kaffefilter, Tomatpure")

    def test_empty_basket_says_so(self):
        self.assertEqual(Basket().summary(), "Korgen: tom")

    def test_a_product_needs_both_ean_and_name(self):
        for ean, name in ((None, "Tomatpure"), (EAN_A, None), ("", "x"), (EAN_A, "")):
            with self.assertRaises(ValueError):
                Basket().add(ean, name)


if __name__ == "__main__":
    unittest.main()
