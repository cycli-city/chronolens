"""Seed the regulatory events corpus into Supabase."""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

from app.core.event_correlator import EventCorrelator
from app.core.regulatory_corpus import REGULATORY_EVENTS


def main():
    print("Seeding regulatory events database...")
    correlator = EventCorrelator()
    count = correlator.seed_events(REGULATORY_EVENTS)
    print(f"Seeded {count} events.")
    print("Done.")


if __name__ == "__main__":
    main()