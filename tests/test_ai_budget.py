import unittest

from core.ai_gateway.budget import BudgetConfig, BudgetManager, BudgetState


class BudgetTests(unittest.TestCase):
    def manager(self, state=BudgetState()):
        return BudgetManager(BudgetConfig(10, 5, 2), state)

    def test_allowed_and_register(self):
        manager = self.manager(); self.assertTrue(manager.can_execute(1).allowed)
        self.assertEqual(manager.register_usage(1).hour_spent, 1)

    def test_limits_and_emergency_stop(self):
        self.assertEqual(self.manager(BudgetState(hour_spent=2)).can_execute(1).reason, "hourly_limit_exceeded")
        self.assertEqual(self.manager(BudgetState(day_spent=5)).can_execute(1).reason, "daily_limit_exceeded")
        self.assertEqual(self.manager(BudgetState(month_spent=10)).can_execute(1).reason, "monthly_limit_exceeded")
        manager = BudgetManager(BudgetConfig(10, 5, 2, True)); self.assertFalse(manager.can_execute(0).allowed)

    def test_remaining_and_immutable_types(self):
        manager = self.manager(BudgetState(1, 2, .5)); self.assertEqual(manager.remaining_budget(), (9, 3, 1.5))
        with self.assertRaises((AttributeError, TypeError)):
            BudgetState().day_spent = 1


if __name__ == "__main__": unittest.main()
