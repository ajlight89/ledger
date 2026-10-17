"""Tests for the Money value class."""

import operator
import unittest
from decimal import Decimal, InvalidOperation

from ledger.core.exceptions import (
    CurrencyMismatchError,
    InvalidAmountError,
    InvalidCurrencyError,
)
from ledger.core.money import Money


class MoneyConstructionTest(unittest.TestCase):
    def test_from_string_keeps_exact_value(self) -> None:
        self.assertEqual(Money("19.99").amount, Decimal("19.99"))

    def test_from_int_is_stored_with_two_decimal_places(self) -> None:
        self.assertEqual(str(Money(5).amount), "5.00")

    def test_from_decimal(self) -> None:
        self.assertEqual(Money(Decimal("0.10")).amount, Decimal("0.10"))

    def test_default_currency_is_usd(self) -> None:
        self.assertEqual(Money("1").currency, "USD")

    def test_currency_code_is_upper_cased(self) -> None:
        self.assertEqual(Money("1", "eur").currency, "EUR")

    def test_rounds_half_up_to_cents(self) -> None:
        cases = [
            ("2.345", "2.35"),
            ("2.344", "2.34"),
            ("-2.345", "-2.35"),
            ("0.005", "0.01"),
        ]
        for given, expected in cases:
            with self.subTest(given=given):
                self.assertEqual(str(Money(given).amount), expected)

    def test_negative_zero_becomes_zero(self) -> None:
        self.assertEqual(str(Money("-0.001").amount), "0.00")


class MoneyInvalidInputTest(unittest.TestCase):
    def test_rejects_float(self) -> None:
        with self.assertRaises(InvalidAmountError):
            Money(0.1)  # type: ignore[arg-type]

    def test_rejects_bool(self) -> None:
        with self.assertRaises(InvalidAmountError):
            Money(True)

    def test_rejects_other_types(self) -> None:
        for bad in (None, [1], b"1"):
            with self.subTest(bad=bad), self.assertRaises(InvalidAmountError):
                Money(bad)  # type: ignore[arg-type]

    def test_rejects_text_that_is_not_number(self) -> None:
        for bad in ("abc", "", "1,000", "$5"):
            with self.subTest(bad=bad), self.assertRaises(InvalidAmountError):
                Money(bad)

    def test_rejects_non_finite_values(self) -> None:
        for bad in ("NaN", "Infinity", "-inf", "sNaN"):
            with self.subTest(bad=bad), self.assertRaises(InvalidAmountError):
                Money(bad)

    def test_rejects_amount_too_large(self) -> None:
        with self.assertRaises(InvalidAmountError):
            Money("1e30")

    def test_error_keeps_original_cause(self) -> None:
        with self.assertRaises(InvalidAmountError) as caught:
            Money("abc")
        self.assertIsInstance(caught.exception.__cause__, InvalidOperation)

    def test_rejects_bad_currency_codes(self) -> None:
        for bad in ("US", "USDX", "U$D", "", "ÉUR", 840):
            with self.subTest(bad=bad), self.assertRaises(InvalidCurrencyError):
                Money("1", bad)  # type: ignore[arg-type]


class MoneyImmutabilityTest(unittest.TestCase):
    def test_amount_is_read_only(self) -> None:
        m = Money("1")
        with self.assertRaises(AttributeError):
            m.amount = Decimal(2) # type: ignore[misc]

    def test_currency_is_read_only(self) -> None:
        m = Money("1")
        with self.assertRaises(AttributeError):
            m.currency = "EUR"  # type: ignore[misc]

    def test_cannot_add_new_attributes(self) -> None:
        m = Money("1")
        with self.assertRaises(AttributeError):
            m.note = "lunch" # type: ignore[attr-defined]


class MoneyTextTest(unittest.TestCase):
    def test_repr_is_exact(self) -> None:
        self.assertEqual(repr(Money("19.9")), "Money('19.90', 'USD')")

    def test_str_usd_uses_symbol_and_separator(self) -> None:
        self.assertEqual(str(Money("1234.5")), "$1,234.50")

    def test_str_neg_puts_sign_before_symbol(self) -> None:
        self.assertEqual(str(Money("-42.17")), "-$42.17")

    def test_str_oth_symbol_and_plain_codes(self) -> None:
        self.assertEqual(str(Money("1234.5", "EUR")), "€1,234.50")
        self.assertEqual(str(Money("-10", "CAD")), "-10.00 CAD")

    def test_print_and_f_strings_use_str(self) -> None:
        money = Money("5")
        self.assertEqual(f"{money}", "$5.00")
        self.assertEqual(f"{money!r}", "Money('5.00', 'USD')")


class MoneyEqualityTest(unittest.TestCase):
    def test_equal_when_amount_and_currency_match(self) -> None:
        self.assertEqual(Money("1.5"), Money("1.50"))

    def test_equal_regardless_of_input_type(self) -> None:
        self.assertEqual(Money(5), Money("5.00"))
        self.assertEqual(Money(5), Money(Decimal(5)))

    def test_not_equal_when_amounts_differ(self) -> None:
        self.assertNotEqual(Money("1.00"), Money("1.01"))

    def test_diff_currencies_are_unequal_without_raising(self) -> None:
        self.assertNotEqual(Money("1", "USD"), Money("1", "EUR"))
        
    def test_never_equal_to_plain_nums_or_text(self) -> None:
        for other in (5, Decimal(5), "5.00", None):
            with self.subTest(other=other):
                self.assertFalse(Money("5") == other)
                self.assertTrue(Money("5") != other)

    def test_eq_returns_notimplemented_for_other_types(self) -> None:
        self.assertIs(Money("5").__eq__(5), NotImplemented)

    def test_not_equal_operator_is_derived_from_eq(self) -> None:
        self.assertTrue(Money("1") != Money("2"))
        self.assertFalse(Money("1") != Money("1.00"))

    def test_equal_values_have_equal_hashes(self) -> None:
        self.assertEqual(hash(Money("1.5")), hash(Money("1.50")))

    def test_usable_in_sets_and_as_dict_keys(self) -> None:
        self.assertEqual(len({Money("1"), Money("1.00"), Money("2")}), 2)
        labels = {Money("1"): "one"}
        self.assertEqual(labels[Money("1.00")], "one")

    def test_repr_round_trips_through_eval(self) -> None:
        original = Money("-42.17", "EUR")
        self.assertEqual(eval(repr(original), {"Money": Money}), original)


class MoneyArithmeticTest(unittest.TestCase):
    def test_add_same_currency(self) -> None:
        self.assertEqual(Money("1.25") + Money("2.50"), Money("3.75"))

    def test_subtraction_can_go_negative(self) -> None:
        self.assertEqual(Money("5") - Money("7.50"), Money("-2.50"))

    def test_mixing_currencies_raises_currency_mismatch(self) -> None:
        for op in (operator.add, operator.sub):
            with self.subTest(op=op.__name__):
                with self.assertRaises(CurrencyMismatchError) as caught:
                    op(Money("1", "USD"), Money("1", "EUR"))
                self.assertEqual(
                    (caught.exception.left, caught.exception.right), ("USD", "EUR"))

    def test_add_returns_new_object_and_leaves_operands_unchanged(self) -> None:
        a, b = Money("1"), Money("2")
        total = a + b
        self.assertIsNot(total, a)
        self.assertEqual((a, b), (Money("1"), Money("2")))

    def test_in_place_add_rebinds_name_without_changing_original(self) -> None:
        a = Money("1")
        original = a
        a += Money("2")
        self.assertEqual(a, Money("3"))
        self.assertEqual(original, Money("1"))

    def test_add_or_subtract_plain_values_raises_type_error(self) -> None:
        for op in (operator.add, operator.sub):
            for other in (5, Decimal(5), "5"):
                with self.subTest(op=op.__name__, other=other):
                    with self.assertRaises(TypeError):
                        op(Money("1"), other)
                    with self.assertRaises(TypeError):
                        op(other, Money("1"))

    def test_negation_flips_sign_and_keeps_currency(self) -> None:
        self.assertEqual(-Money("4.20", "EUR"), Money("-4.20", "EUR"))
        self.assertEqual(-Money("-4.20"), Money("4.20"))

    def test_negating_zero_gives_zero(self) -> None:
        self.assertEqual(str(-Money("0")), "$0.00")

    def test_multiply_by_int_and_decimal(self) -> None:
        self.assertEqual(Money("10.00") * 3, Money("30.00"))
        self.assertEqual(Money("10") * Decimal("1.5"), Money("15"))

    def test_multiply_works_from_either_side(self) -> None:
        self.assertEqual(3 * Money("2.50"), Money("7.50"))
        self.assertEqual(Decimal("0.5") * Money("3"), Money("1.50"))

    def test_multiply_rounds_half_up_to_cents(self) -> None:
        self.assertEqual(Money("10.00") * Decimal("0.0125"), Money("0.13"))
        self.assertEqual(Money("0.10") * Decimal("0.333"), Money("0.03"))

    def test_multiply_rejects_float_bool_money_and_text(self) -> None:
        for factor in (1.5, True, Money("2"), "2"):
            with self.subTest(factor=factor):
                with self.assertRaises(TypeError):
                    Money("1") * factor  # type: ignore[operator]
                with self.assertRaises(TypeError):
                    factor * Money("1")  # type: ignore[operator]

    def test_sum_needs_a_money_start_value(self) -> None:
        items = [Money("1"), Money("2")]
        with self.assertRaises(TypeError):
            sum(items) # type: ignore[arg-type]
        self.assertEqual(sum(items, start=Money("0")), Money("3"))
        self.assertEqual(sum([], start=Money("0", "EUR")), Money("0", "EUR"))

class MoneyOrderingTest(unittest.TestCase):
    def test_less_than_and_greater_than(self) -> None:
        self.assertTrue(Money("1") < Money("2"))
        self.assertTrue(Money("2") > Money("1"))
        self.assertFalse(Money("2") < Money("1"))

    def test_less_equal_and_greater_equal_include_equal_values(self) -> None:
        self.assertTrue(Money("1") <= Money("1.00"))
        self.assertTrue(Money("1") >= Money("1.00"))
        self.assertTrue(Money("1") <= Money("2"))
        self.assertFalse(Money("1") >= Money("2"))

    def test_negative_amounts_order_below_positive(self) -> None:
        self.assertTrue(Money("-5") < Money("0") < Money("5"))

    def test_lt_returns_notimplemented_for_other_types(self) -> None:
        self.assertIs(Money("1").__lt__(5), NotImplemented) # type: ignore[arg-type]

    def test_comparing_different_currencies_raises(self) -> None:
        for op in (operator.lt, operator.le, operator.gt, operator.ge):
            with self.subTest(op=op.__name__), self.assertRaises(CurrencyMismatchError):
                op(Money("1", "USD"), Money("1", "EUR"))

    def test_comparing_with_plain_numbers_raises_type_error(self) -> None:
        for op in (operator.lt, operator.le, operator.gt, operator.ge):
            for other in (5, Decimal(5)):
                with self.subTest(op=op.__name__, other=other):
                    with self.assertRaises(TypeError):
                        op(Money("1"), other)
                    with self.assertRaises(TypeError):
                        op(other, Money("1"))

    def test_sorted_min_and_max_work_within_one_currency(self) -> None:
        items = [Money("3"), Money("-1"), Money("2")]
        self.assertEqual(sorted(items), [Money("-1"), Money("2"), Money("3")])
        self.assertEqual(min(items), Money("-1"))
        self.assertEqual(max(items), Money("3"))

    def test_sorting_mixed_currencies_raises(self) -> None:
        with self.assertRaises(CurrencyMismatchError):
            sorted([Money("1"), Money("2", "EUR")])