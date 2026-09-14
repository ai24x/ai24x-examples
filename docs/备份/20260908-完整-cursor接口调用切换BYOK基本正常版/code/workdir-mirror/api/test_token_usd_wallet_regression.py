# -*- coding: utf-8 -*-
"""Regression checks for USD-backed spendability when credit lots are empty."""
import sys
from unittest.mock import MagicMock

sys.path.insert(0, ".")

from token_mvp_service import _usd_to_flash_tokens, spendable_tokens


def make_db(usd_cents):
    db = MagicMock()
    lot_query = MagicMock()
    lot_query.filter.return_value.order_by.return_value.all.return_value = []
    wallet_query = MagicMock()
    wallet_query.filter.return_value.first.return_value = (usd_cents,)

    def query(entity):
        name = getattr(entity, "__name__", "")
        return lot_query if name == "TokenCreditLot" else wallet_query

    db.query.side_effect = query
    return db


assert _usd_to_flash_tokens(0) == 0
assert _usd_to_flash_tokens(1603) == 45800000
assert spendable_tokens(make_db(1603), 40) == 45800000
assert spendable_tokens(make_db(0), 40) == 0
print("USD wallet spendability regression: PASS")
