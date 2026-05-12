#!/usr/bin/env python3
"""Optional helper: populate the configured index (``tc_index`` by default) with
a handful of sample documents so you can try the application immediately.

Run it from the project root (with the virtualenv active and Elasticsearch
running)::

    python tools/seed_data.py            # create index (if missing) + insert samples
    python tools/seed_data.py --reset    # delete the index first, then re-seed
    python tools/seed_data.py --force    # bypass the "index already has lots of data" guard

Safety guard
------------
This script refuses to touch a target index that already exists **and** holds
more than ``SAFETY_DOC_LIMIT`` documents, unless ``--force`` is given — so it
cannot accidentally pollute or (with ``--reset``) destroy a populated index.
The sample documents are written with ids prefixed ``sample-`` so they can
never overwrite a real document and are trivial to clean up::

    POST tc_index/_delete_by_query
    {"query": {"ids": {"values": ["sample-1", "sample-2", ..., "sample-8"]}}}

It reuses the same configuration and Elasticsearch client as the GUI, so it
honours your ``.env`` file.  This script is **not** required by the application.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the project root importable when run as ``python tools/seed_data.py``.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.logging_config import configure_logging  # noqa: E402
from app.config.settings import settings  # noqa: E402
from app.database.es_client import ESClient  # noqa: E402

#: If the target index already exists and contains more documents than this,
#: refuse to run unless ``--force`` is passed.
SAFETY_DOC_LIMIT = 1_000

#: Prefix applied to every sample document id (so they never clash with real data).
SAMPLE_ID_PREFIX = "sample-"

SAMPLE_DOCS: list[dict] = [
    {"name": "Ali Hassan", "email": "ali.hassan@example.com", "phone": "+92 300 5550101",
     "address": {"street": "12 Mango Road", "city": "Lahore", "province": "Punjab", "country": "Pakistan"},
     "gender": "Male", "date_of_birth": "1989-04-12", "company": "Indus Trading Co.",
     "designation": "Procurement Manager", "tags": ["vip", "wholesale"]},
    {"name": "Sara Ahmed", "email": "sara.ahmed@example.org", "phone": "+44 20 7946 0102",
     "address": {"street": "8 Baker Street", "city": "London", "postal_code": "W1U 6TU", "country": "United Kingdom"},
     "gender": "Female", "date_of_birth": "1992-11-03", "company": "Northwind Logistics",
     "designation": "Account Executive", "tags": ["retail"]},
    {"name": "John Doe", "email": "john.doe@example.com", "phone": "+1 (212) 555-0103",
     "address": {"street": "1 Park Avenue", "city": "New York", "state": "NY", "postal_code": "10016", "country": "USA"},
     "gender": "Male", "date_of_birth": "1985-07-21", "company": "Acme Corp.",
     "designation": "Operations Lead", "tags": ["new"]},
    {"name": "Mei Lin", "email": "mei.lin@example.net", "phone": "+86 21 5555 0104",
     "address": {"street": "99 Nanjing Road", "city": "Shanghai", "district": "Huangpu", "country": "China"},
     "gender": "Female", "date_of_birth": "1994-02-09", "company": "Pacific Imports",
     "designation": "Supply Chain Analyst", "tags": ["wholesale"]},
    {"name": "Carlos Ruiz Mendoza", "email": "carlos.ruiz@example.com", "phone": "+34 91 555 0105",
     "address": {"street": "5 Gran Via", "city": "Madrid", "postal_code": "28013", "country": "Spain"},
     "gender": "Male", "date_of_birth": "1990-09-30", "company": "Iberia Distribución",
     "designation": "Regional Sales Manager", "tags": []},
    {"name": "Aliyah Khan", "email": "aliyah.khan@example.com", "phone": "+92 311 5550106",
     "address": {"street": "21 Liberty Market", "city": "Lahore", "province": "Punjab", "country": "Pakistan"},
     "gender": "Female", "date_of_birth": "1996-06-18", "company": "Crescent Textiles",
     "designation": "Marketing Associate", "tags": ["vip"]},
    {"name": "Robert Smith", "email": "rob.smith@example.io", "phone": "+1 415 555 0107",
     "address": {"street": "700 Market Street", "city": "San Francisco", "state": "CA", "postal_code": "94103", "country": "USA"},
     "gender": "Male", "date_of_birth": "1983-12-02", "company": "Bayline Software",
     "designation": "Senior Engineer", "tags": ["retail", "new"]},
    {"name": "Fatima Noor", "email": "fatima.noor@example.com", "phone": "+971 4 555 0108",
     "address": {"street": "3 Sheikh Zayed Road", "city": "Dubai", "country": "United Arab Emirates"},
     "gender": "Female", "date_of_birth": "1991-03-27", "company": "Gulf Retail Group",
     "designation": "Store Director", "tags": ["vip"]},
]

SAMPLE_MAPPING = {
    "properties": {
        "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        "email": {"type": "keyword"},
        "phone": {"type": "keyword"},
        "gender": {"type": "keyword"},
        "date_of_birth": {"type": "date"},
        "company": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        "designation": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        "tags": {"type": "keyword"},
        "address": {
            "properties": {
                "street": {"type": "text"},
                "city": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "district": {"type": "keyword"},
                "state": {"type": "keyword"},
                "province": {"type": "keyword"},
                "postal_code": {"type": "keyword"},
                "country": {"type": "keyword"},
            }
        },
    }
}

# Exit codes
EXIT_OK = 0
EXIT_NO_ES = 1
EXIT_GUARD = 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed sample data into the configured Elasticsearch index (safe by default).",
    )
    parser.add_argument("--reset", action="store_true",
                        help="delete the index before seeding (requires --force on a populated index)")
    parser.add_argument("--force", action="store_true",
                        help=f"bypass the safety guard that protects indices with more than {SAFETY_DOC_LIMIT:,} docs")
    parser.add_argument("--index", default=settings.es_index,
                        help=f"target index (default: {settings.es_index})")
    args = parser.parse_args()

    log = configure_logging()
    es = ESClient.instance().client
    index: str = args.index

    if not es.ping():
        log.error("Cannot reach Elasticsearch at %s — is it running?", settings.es_host)
        return EXIT_NO_ES

    exists = bool(es.indices.exists(index=index))
    existing_count = int(dict(es.count(index=index)).get("count", 0)) if exists else 0

    # ---- safety guard ----------------------------------------------------
    if exists and existing_count > SAFETY_DOC_LIMIT and not args.force:
        action = "delete and recreate" if args.reset else "write sample documents into"
        log.error(
            "Refusing to %s index %r — it already contains %s document(s) (limit: %s).",
            action, index, f"{existing_count:,}", f"{SAFETY_DOC_LIMIT:,}",
        )
        print(
            f"\n[!] Aborted: index '{index}' already holds {existing_count:,} document(s).\n"
            f"    This looks like a real / populated index, so the seeder will not touch it.\n"
            f"    If you really mean to {action} it, re-run with --force:\n"
            f"        python tools/seed_data.py{' --reset' if args.reset else ''} --force --index {index}\n",
            file=sys.stderr,
        )
        return EXIT_GUARD

    # ---- (optionally) reset ---------------------------------------------
    if args.reset and exists:
        log.warning("Deleting existing index %r (had %s document(s))", index, f"{existing_count:,}")
        es.indices.delete(index=index)
        exists = False

    # ---- create the index if needed -------------------------------------
    if not exists:
        log.info("Creating index %r with the sample mapping", index)
        es.indices.create(index=index, mappings=SAMPLE_MAPPING)

    # ---- insert the sample documents (prefixed ids -> never overwrite real data)
    inserted = 0
    for i, doc in enumerate(SAMPLE_DOCS, start=1):
        es.index(index=index, id=f"{SAMPLE_ID_PREFIX}{i}", document=doc)
        inserted += 1
    es.indices.refresh(index=index)

    total = int(dict(es.count(index=index)).get("count", 0))
    sample_ids = [f"{SAMPLE_ID_PREFIX}{i}" for i in range(1, inserted + 1)]
    log.info("Done. Inserted %d sample doc(s); index %r now has %s document(s).", inserted, index, f"{total:,}")
    print(
        f"Seeded {inserted} sample document(s) (ids '{sample_ids[0]}'..'{sample_ids[-1]}'); "
        f"index '{index}' total count = {total:,}"
    )
    ids_json = ", ".join(f'"{sid}"' for sid in sample_ids)
    print(
        "To remove them later:\n"
        f"  curl -k -u {settings.es_username}:<password> -XPOST "
        f'"{settings.es_host}/{index}/_delete_by_query?refresh=true" '
        "-H 'Content-Type: application/json' "
        f"-d '{{\"query\": {{\"ids\": {{\"values\": [{ids_json}]}}}}}}'"
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
