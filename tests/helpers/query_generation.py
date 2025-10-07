# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

import datetime
import random

# Prompt source: keep it simple here; you can import your generator
ASSETS = [
    "S&P 500", "Bitcoin", "Ethereum", "Gold", "Silver",
    "Oil", "NASDAQ 100", "Dow Jones", "EUR/USD", "GBP/USD",
]
THRESHOLDS = ["4,500", "5,000", "10,000", "50,000", "2,000"]
DURATIONS = [
    "tomorrow", "in 3 days", "next Monday", "by end of the week",
    "by the end of the month",
]
EVENTS = [
    "closes above", "drops below", "volatility exceeds",
    "volume exceeds", "daily range exceeds",
]
TEMPLATES = [
    "What is the probability that {asset} {event} {threshold} {when}?",
    "Estimate the chance that {asset} {event} {threshold} {when}.",
    "What are the odds that {asset} {event} {threshold} {when}?",
    "By what probability will {asset} {event} {threshold} {when}?",
]

def next_n_business_days(start: datetime.date, n: int):
    days = []
    d = start
    while len(days) < n:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:
            days.append(d.isoformat())
    return days

DATES = next_n_business_days(datetime.date.today(), 100)

def make_prompts(n: int):
    pool = []
    while len(pool) < n:
        asset = random.choice(ASSETS)
        event = random.choice(EVENTS)
        threshold = random.choice(THRESHOLDS)
        when = random.choice(DATES + DURATIONS)
        template = random.choice(TEMPLATES)
        pool.append(template.format(
            asset=asset,
            event=event,
            threshold=threshold,
            when=when,
        ))
    return pool