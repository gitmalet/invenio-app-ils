# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2019 CERN.
#
# invenio-app-ils is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""CLI for Invenio App ILS."""

import json
import os
import random
import re
from datetime import datetime, timedelta
from random import randint

import arrow
import click
import lorem
from flask import current_app
from flask.cli import with_appcontext
from invenio_accounts.models import User
from invenio_circulation.api import Loan
from invenio_circulation.pidstore.pids import CIRCULATION_LOAN_PID_TYPE
from invenio_db import db
from invenio_indexer.api import RecordIndexer
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_pidstore.providers.recordid_v2 import RecordIdProviderV2
from invenio_search import current_search
from invenio_userprofiles.models import UserProfile
from lorem.text import TextLorem

from invenio_app_ils.patrons.indexer import PatronIndexer

from .acquisition.api import ORDER_PID_TYPE, VENDOR_PID_TYPE, Order, Vendor
from .document_requests.api import DOCUMENT_REQUEST_PID_TYPE, DocumentRequest
from .documents.api import DOCUMENT_PID_TYPE, Document
from .ill.api import BORROWING_REQUEST_PID_TYPE, LIBRARY_PID_TYPE, \
    BorrowingRequest, Library
from .pidstore.pids import EITEM_PID_TYPE, INTERNAL_LOCATION_PID_TYPE, \
    ITEM_PID_TYPE, LOCATION_PID_TYPE, SERIES_PID_TYPE
from .records.api import EItem, InternalLocation, Item, Location, Patron, \
    Series
from .records_relations.api import RecordRelationsParentChild, \
    RecordRelationsSiblings
from .relations.api import Relation


def minter(pid_type, pid_field, record):
    """Mint the given PID for the given record."""
    pid = PersistentIdentifier.get(
        pid_type="recid",
        pid_value=record[pid_field]
    )
    pid.status = PIDStatus.REGISTERED
    pid.object_type = "rec"
    pid.object_uuid = record.id
    pid.pid_type = pid_type


class Holder(object):
    """Hold generated data."""

    def __init__(
        self,
        patrons_pids,
        languages,
        librarian_pid,
        tags,
        total_intloc,
        total_items,
        total_eitems,
        total_documents,
        total_loans,
        total_series,
        total_document_requests,
        total_vendors,
        total_orders,
        total_borrowing_requests,
        total_libraries
    ):
        """Constructor."""
        self.patrons_pids = patrons_pids
        self.languages = languages
        self.librarian_pid = librarian_pid
        self.tags = tags
        self.location = {}
        self.internal_locations = {"objs": [], "total": total_intloc}
        self.items = {"objs": [], "total": total_items}
        self.eitems = {"objs": [], "total": total_eitems}
        self.documents = {"objs": [], "total": total_documents}
        self.loans = {"objs": [], "total": total_loans}
        self.series = {"objs": [], "total": total_series}
        self.related_records = {"objs": [], "total": 0}
        self.document_requests = {"objs": [], "total": total_document_requests}
        self.vendors = {"objs": [], "total": total_vendors}
        self.orders = {"objs": [], "total": total_orders}
        self.borrowing_requests = {"objs": [], "total": total_borrowing_requests}
        self.libraries = {"objs": [], "total": total_libraries}

    def pids(self, collection, pid_field):
        """Get a list of PIDs for a collection."""
        return [obj[pid_field] for obj in getattr(self, collection)["objs"]]


class Generator(object):
    """Generator."""

    def __init__(self, holder, minter):
        """Constructor."""
        self.holder = holder
        self.minter = minter

    def create_pid(self):
        """Create a new persistent identifier."""
        return RecordIdProviderV2.create().pid.pid_value

    def _persist(self, pid_type, pid_field, record):
        """Mint PID and store in the db."""
        minter(pid_type, pid_field, record)
        record.commit()
        return record


class LocationGenerator(Generator):
    """Location Generator."""

    def generate(self):
        """Generate."""
        self.holder.location = {
            "pid": self.create_pid(),
            "name": "Central Library",
            "address": "Rue de Meyrin",
            "email": "library@cern.ch",
        }

    def persist(self):
        """Persist."""
        record = Location.create(self.holder.location)
        return self._persist(LOCATION_PID_TYPE, "pid", record)


class InternalLocationGenerator(Generator):
    """InternalLocation Generator."""

    def generate(self):
        """Generate."""
        size = self.holder.internal_locations["total"]
        location_pid_value = self.holder.location["pid"]
        objs = [
            {
                "pid": self.create_pid(),
                "legacy_id": "{}".format(randint(100000, 999999)),
                "name": "Building {}".format(randint(1, 10)),
                "notes": lorem.sentence(),
                "physical_location": lorem.sentence(),
                "location_pid": location_pid_value,
            }
            for pid in range(1, size + 1)
        ]

        self.holder.internal_locations["objs"] = objs

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.internal_locations["objs"]:
            rec = self._persist(
                INTERNAL_LOCATION_PID_TYPE, "pid", InternalLocation.create(obj)
            )
            recs.append(rec)
        db.session.commit()
        return recs


class ItemGenerator(Generator):
    """Item Generator."""

    def generate(self):
        """Generate."""
        size = self.holder.items["total"]
        iloc_pids = self.holder.pids("internal_locations", "pid")
        doc_pids = self.holder.pids("documents", "pid")
        shelf_lorem = TextLorem(wsep='-', srange=(2, 3),
                                words='Ax Bs Cw 8080'.split())
        objs = [
            {
                "pid": self.create_pid(),
                "document_pid": random.choice(doc_pids),
                "internal_location_pid": random.choice(iloc_pids),
                "legacy_id": "{}".format(randint(100000, 999999)),
                "legacy_library_id": "{}".format(randint(5, 50)),
                "barcode": "{}".format(randint(10000000, 99999999)),
                "shelf": "{}".format(shelf_lorem.sentence()),
                "description": "{}".format(lorem.text()),
                "internal_notes": "{}".format(lorem.text()),
                "medium": random.choice(Item.MEDIUMS),
                "status": random.choice(
                    random.choices(population=Item.STATUSES,
                                   weights=[0.7, 0.1, 0.1, 0.1, 0.05],
                                   k=10
                                   )),
                "circulation_restriction": random.choice(
                    Item.CIRCULATION_RESTRICTIONS
                ),
            }
            for pid in range(1, size + 1)
        ]

        self.holder.items["objs"] = objs

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.items["objs"]:
            rec = self._persist(ITEM_PID_TYPE, "pid", Item.create(obj))
            recs.append(rec)
        db.session.commit()
        return recs


class EItemGenerator(Generator):
    """EItem Generator."""

    def generate(self):
        """Generate."""
        size = self.holder.eitems["total"]
        doc_pids = self.holder.pids("documents", "pid")

        objs = [
            {
                "pid": self.create_pid(),
                "document_pid": random.choice(doc_pids),
                "description": "{}".format(lorem.text()),
                "internal_notes": "{}".format(lorem.text()),
                "urls": [
                    {
                        "value": "https://home.cern/science/physics/dark-matter",
                        "description": "Dark matter"
                    },
                    {
                        "value": "https://home.cern/science/physics/antimatter",
                        "description": "Anti matter"
                    },
                ],
                "open_access": bool(random.getrandbits(1)),
            }
            for pid in range(1, size + 1)
        ]

        self.holder.eitems["objs"] = objs

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.eitems["objs"]:
            rec = self._persist(EITEM_PID_TYPE, "pid", EItem.create(obj))
            recs.append(rec)
        db.session.commit()
        return recs


class DocumentGenerator(Generator):
    """Document Generator."""

    PERIODICAL_ISSUE = "PERIODICAL_ISSUE"
    AUTHORS = [
        {"full_name": "Close, Frank"},
        {"full_name": "CERN", "type": "ORGANISATION"},
        {
            "full_name": "Doe, Jane",
            "affiliations": [{
                "name": "Imperial Coll., London",
                "identifiers": [{"scheme": "ROR", "value": "12345"}]
            }],
            "identifiers": [{"scheme": "ORCID", "value": "1234AAA"}],
            "roles": ["editor"]
        },
        {
            "full_name": "Doe, John", "roles": ["AUTHOR"],
            "affiliations": [{"name": "CERN"}]
        },
    ]
    CONFERENCE_INFO = {
        "acronym": "CHEP",
        "country": "AU",
        "dates": "1 - 20 Nov. 2019",
        "identifiers": [{"scheme": "OTHER", "value": "CHEP2019"}],
        "place": "Adelaide",
        "series": "CHEP",
        "title": "Conference on Computing in High Energy Physics",
        "year": 2019,
    }
    IMPRINTS = [
        {"date": "2019-08-02", "place": "Geneva", "publisher": "CERN"},
        {"date": "2017-08-02", "place": "Hamburg", "publisher": "Springer"},
    ]

    def generate_document(self, index, **kwargs):
        """Generate document data."""
        publication_year = kwargs.get("publication_year", str(randint(1700, 2020)))
        imprint = random.choice(self.IMPRINTS)
        obj = {
            "pid": self.create_pid(),
            "title": lorem.sentence(),
            "authors": random.sample(self.AUTHORS, randint(1, 3)),
            "abstract": "{}".format(lorem.text()),
            "document_type": random.choice(Document.DOCUMENT_TYPES),
            "languages": [
                lang["key"]
                for lang in random.sample(self.holder.languages, randint(1, 3))
            ],
            "table_of_content": ["{}".format(lorem.sentence())],
            "note": "{}".format(lorem.text()),
            "tags": [tag["key"] for tag in random.sample(
                self.holder.tags,
                randint(1, len(self.holder.tags) - 1))
            ],
            "edition": str(index),
            "keywords": {
                "source": lorem.sentence(),
                "value": lorem.sentence()
            },
            "conference_info": self.CONFERENCE_INFO,
            "number_of_pages": str(random.randint(0, 300)),
            "imprint": {
                **imprint,
                "date": "{}-08-02".format(publication_year)
            },
            "publication_year": publication_year,
            "urls": [
                {
                    "description": "{}".format(lorem.sentence()),
                    "value": "http://random.url"
                }
            ],
            "open_access": True,
        }
        obj.update(**kwargs)
        return obj

    def generate(self):
        """Generate."""
        size = self.holder.documents["total"]

        objs = [
            self.generate_document(index)
            for index in range(1, size + 1)
        ]

        # Generate periodical issues
        volume = 1
        issue = 1
        publication_year = randint(1700, 2000)
        for index in range(1, 11):
            objs.append(self.generate_document(
                index,
                document_type=self.PERIODICAL_ISSUE,
                title="Volume {} Issue {}".format(volume, issue),
                publication_year=str(publication_year),
            ))
            if issue == 3:
                issue = 1
                volume += 1
                publication_year += 1
            else:
                issue += 1

        self.holder.documents["objs"] = objs

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.documents["objs"]:
            rec = self._persist(DOCUMENT_PID_TYPE, "pid", Document.create(obj))
            recs.append(rec)
        db.session.commit()
        return recs


class LoanGenerator(Generator):
    """Loan Generator."""

    LOAN_STATES = ["PENDING", "ITEM_ON_LOAN", "ITEM_RETURNED", "CANCELLED"]

    def _get_item_can_circulate(self, items):
        """Return an item that can circulate."""
        item = items[randint(1, len(items) - 1)]
        if item["status"] != "CAN_CIRCULATE":
            return self._get_item_can_circulate(items)
        return item

    def _get_valid_status(self, item, items_on_loan):
        """Return valid loan status for the item to avoid inconsistencies."""
        # cannot have 2 loans in the same item
        if item["pid"] in items_on_loan:
            status = self.LOAN_STATES[0]
        else:
            status = self.LOAN_STATES[randint(0, 3)]
        return status

    def _fill_loan_with_valid_request(self, loan):
        """Add fields to the loan with dates valid for a request."""
        transaction_date = arrow.utcnow() - timedelta(days=randint(1, 10))
        request_start_date = transaction_date + timedelta(days=15)
        request_expire_date = transaction_date + timedelta(days=180)
        loan["transaction_date"] = transaction_date.isoformat()
        loan["request_start_date"] = request_start_date.date().isoformat()
        loan["request_expire_date"] = request_expire_date.date().isoformat()

    def _fill_loan_with_valid_loan(self, loan):
        """Add fields to the loan with dates valid for a on-going loan."""
        transaction_date = arrow.utcnow() - timedelta(days=randint(10, 30))
        start_date = transaction_date - timedelta(days=randint(1, 5))
        end_date = start_date + timedelta(days=30)
        loan["transaction_date"] = transaction_date.isoformat()
        loan["start_date"] = start_date.date().isoformat()
        loan["end_date"] = end_date.date().isoformat()
        loan["extension_count"] = randint(0, 3)

    def _fill_loan_with_loan_returned(self, loan):
        """Add fields to the loan with dates valid for a returned loan."""
        transaction_date = arrow.utcnow() - timedelta(days=randint(50, 70))
        start_date = transaction_date - timedelta(days=randint(40, 50))
        end_date = start_date + timedelta(days=30)
        loan["transaction_date"] = transaction_date.isoformat()
        loan["start_date"] = start_date.date().isoformat()
        loan["end_date"] = end_date.date().isoformat()

    def _fill_loan_with_loan_cancelled(self, loan):
        """Add fields to the loan with dates valid for a cancelled loan."""
        transaction_date = arrow.utcnow() - timedelta(days=randint(50, 100))
        request_expire_date = transaction_date + timedelta(days=180)
        start_date = transaction_date - timedelta(days=randint(40, 50))
        end_date = start_date + timedelta(days=30)
        loan["transaction_date"] = transaction_date.isoformat()
        loan["request_expire_date"] = request_expire_date.date().isoformat()
        loan["start_date"] = start_date.date().isoformat()
        loan["end_date"] = end_date.date().isoformat()
        loan["cancel_reason"] = "{}".format(lorem.sentence())

    def _fill_loan(self, loan):
        """Fill loan with valid dates."""
        if loan["state"] == "PENDING":
            self._fill_loan_with_valid_request(loan)
        elif loan["state"] == "ITEM_ON_LOAN":
            self._fill_loan_with_valid_loan(loan)
        elif loan["state"] == "ITEM_RETURNED":
            self._fill_loan_with_loan_returned(loan)
        elif loan["state"] == "CANCELLED":
            self._fill_loan_with_loan_cancelled(loan)
        return loan

    def generate(self):
        """Generate."""
        size = self.holder.loans["total"]
        loc_pid = self.holder.location["pid"]
        items = self.holder.items["objs"]
        patrons_pids = self.holder.patrons_pids
        librarian_pid = self.holder.librarian_pid
        doc_pids = self.holder.pids("documents", "pid")
        all_delivery_methods = list(
            current_app.config["CIRCULATION_DELIVERY_METHODS"].keys()
        )
        delivery = all_delivery_methods[randint(0, 1)]

        items_on_loan = []
        for pid in range(1, size + 1):
            item = self._get_item_can_circulate(items)
            item_state = self._get_valid_status(item, items_on_loan)
            patron_id = random.choice(patrons_pids)

            loan = {
                "pid": self.create_pid(),
                "document_pid": random.choice(doc_pids),
                "patron_pid": "{}".format(patron_id),
                "pickup_location_pid": "{}".format(loc_pid),
                "state": "{}".format(item_state),
                "transaction_location_pid": "{}".format(loc_pid),
                "transaction_user_pid": "{}".format(librarian_pid),
                "delivery": {"method": delivery},
            }
            loan = self._fill_loan(loan)

            if item_state != "PENDING":
                loan["item_pid"] = {
                    "type": ITEM_PID_TYPE,
                    "value": item["pid"]
                }
                items_on_loan.append(item["pid"])

            self.holder.loans["objs"].append(loan)

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.loans["objs"]:
            rec = self._persist(
                CIRCULATION_LOAN_PID_TYPE, "pid", Loan.create(obj)
            )
            recs.append(rec)
        db.session.commit()
        return recs


class SeriesGenerator(Generator):
    """Series Generator."""

    MODE_OF_ISSUANCE = ["MULTIPART_MONOGRAPH", "SERIAL"]

    def random_issn(self):
        """Generate a random ISSN."""
        random_4digit = [randint(1000, 9999), randint(1000, 9999)]
        return "-".join(str(r) for r in random_4digit)

    def random_multipart(self, obj, index):
        """Randomize multipart data."""
        obj["edition"] = str(index)
        for _ in range(randint(1, 2)):
            obj["identifiers"].append(dict(
                scheme="ISBN",
                value=self.random_issn()
            ))

    def random_serial(self, obj):
        """Randomize serial data."""
        for _ in range(randint(1, 3)):
            obj["identifiers"].append(dict(
                material=random.choice(["ONLINE", "PRINT"]),
                scheme="ISSN",
                value=self.random_issn()
            ))
        obj["abbreviated_title"] = obj["title"].split()[0]
        obj["alternative_titles"] = [
            dict(
                value=obj["title"],
                type="SUBTITLE"
            ),
            dict(
                value=obj["title"],
                type="TRANSLATED_TITLE",
                language="FR",
                source="CERN"
            )
        ]
        obj["internal_notes"] = [
            dict(
                field="title",
                user="Test",
                value="Internal test note."
            )
        ]
        obj["notes"] = lorem.text()
        obj["publisher"] = lorem.sentence().split()[0]
        obj["access_urls"] = [
            dict(
                open_access=True,
                description=lorem.sentence(),
                value="https://home.cern/"
            )
            for _ in range(1, 3)
        ]
        obj["urls"] = [
            dict(
                description=lorem.sentence(),
                value="https://home.cern/"
            )
            for _ in range(1, 3)
        ]

    def generate_minimal(self, objs):
        """Generate a series with only the required fields."""
        objs.append({
            "pid": self.create_pid(),
            "mode_of_issuance": "SERIAL",
            "title": "Minimal Series",
        })

    def generate(self):
        """Generate."""
        size = self.holder.series["total"]
        objs = []
        self.generate_minimal(objs)
        for index in range(1, size + 1):
            moi = random.choice(self.MODE_OF_ISSUANCE)
            authors = random.sample(DocumentGenerator.AUTHORS, len(DocumentGenerator.AUTHORS))
            obj = {
                "pid": self.create_pid(),
                "mode_of_issuance": moi,
                "title": lorem.sentence(),
                "authors": [author["full_name"] for author in authors],
                "abstract": lorem.text(),
                "languages": [
                    lang["key"]
                    for lang in random.sample(
                        self.holder.languages, randint(1, 3)
                    )
                ],
                "identifiers": [],
            }
            if moi == "SERIAL":
                self.random_serial(obj)
            elif moi == "MULTIPART_MONOGRAPH":
                self.random_multipart(obj, index)
            objs.append(obj)

        self.holder.series["objs"] = objs

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.series["objs"]:
            rec = self._persist(SERIES_PID_TYPE, "pid", Series.create(obj))
            recs.append(rec)
        db.session.commit()
        return recs


class RecordRelationsGenerator(Generator):
    """Related records generator."""

    @staticmethod
    def random_series(series, moi):
        """Get a random series with a specific mode of issuance."""
        for s in random.sample(series, len(series)):
            if s["mode_of_issuance"] == moi:
                return s

    def generate_parent_child_relations(self, documents, series):
        """Generate parent-child relations."""
        def random_docs():
            docs = [
                doc
                for doc in documents
                if doc["document_type"] != "PERIODICAL_ISSUE"
            ]
            return random.sample(docs, randint(1, min(5, len(docs))))

        objs = self.holder.related_records["objs"]
        serial_parent = self.random_series(series, "SERIAL")
        multipart_parent = self.random_series(series, "MULTIPART_MONOGRAPH")
        multipart_children = random_docs()

        serial_children = []
        for document in documents:
            if document["document_type"] == "PERIODICAL_ISSUE":
                serial_children.append(document)

        objs.append(serial_parent)
        rr = RecordRelationsParentChild()
        serial_relation = Relation.get_relation_by_name("serial")
        multipart_relation = Relation.get_relation_by_name(
            "multipart_monograph"
        )
        re_volume = re.compile(r'Volume (?P<volume>\d+)', re.IGNORECASE)
        for index, child in enumerate(serial_children):
            m = re_volume.match(child["title"])
            volume = str(index + 1)
            if m:
                volume = m["volume"]
            rr.add(
                serial_parent,
                child,
                relation_type=serial_relation,
                volume=volume,
            )
            objs.append(child)
        for index, child in enumerate(multipart_children):
            rr.add(
                multipart_parent,
                child,
                relation_type=multipart_relation,
                volume="{}".format(index + 1),
            )
            objs.append(child)

    def generate_sibling_relations(self, documents, series):
        """Generate sibling relations."""
        objs = self.holder.related_records["objs"]
        rr = RecordRelationsSiblings()

        def add_random_relations(relation_type):
            random_docs = random.sample(
                documents, randint(2, min(5, len(documents)))
            )

            objs.append(random_docs[0])
            for record in random_docs[1:]:
                rr.add(random_docs[0], record, relation_type=relation_type)
                objs.append(record)

            if relation_type.name == "edition":
                record = self.random_series(series, "MULTIPART_MONOGRAPH")
                rr.add(random_docs[0], record, relation_type=relation_type)
                objs.append(record)

        add_random_relations(Relation.get_relation_by_name("language"))
        add_random_relations(Relation.get_relation_by_name("edition"))

    def generate(self, rec_docs, rec_series):
        """Generate related records."""
        self.generate_parent_child_relations(rec_docs, rec_series)
        self.generate_sibling_relations(rec_docs, rec_series)

    def persist(self):
        """Persist."""
        db.session.commit()
        return self.holder.related_records["objs"]


class DocumentRequestGenerator(Generator):
    """Document requests generator."""

    def random_document_pid(self):
        """Get a random document PID."""
        return random.choice(self.holder.pids("documents", "pid"))

    def generate(self):
        """Generate."""
        size = self.holder.document_requests["total"]
        objs = []
        for pid in range(1, size + 1):
            state = random.choice(DocumentRequest.STATES)
            obj = {
                "pid": self.create_pid(),
                "state": state,
                "patron_pid": random.choice(self.holder.patrons_pids),
                "title": lorem.sentence(),
                "authors": lorem.sentence(),
                "publication_year": randint(1700, 2019),
            }
            if state == "REJECTED":
                obj["reject_reason"] = random.choice(DocumentRequest.REJECT_TYPES)
                if obj["reject_reason"] == "IN_CATALOG":
                    obj["document_pid"] = self.random_document_pid()
            elif state == "ACCEPTED":
                obj["document_pid"] = self.random_document_pid()
            objs.append(obj)

        self.holder.document_requests["objs"] = objs

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.document_requests["objs"]:
            rec = self._persist(
                DOCUMENT_REQUEST_PID_TYPE, "pid", DocumentRequest.create(obj)
            )
            recs.append(rec)
        db.session.commit()
        return recs


class LibraryGenerator(Generator):
    """Location Generator."""

    def generate(self):
        """Generate."""
        size = self.holder.libraries["total"]
        objs = [
            {
                "pid": self.create_pid(),
                "name": lorem.sentence(),
                "notes": "{}".format(lorem.text()),
            }
            for pid in range(1, size + 1)
        ]

        self.holder.libraries["objs"] = objs

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.libraries["objs"]:
            rec = self._persist(
                LIBRARY_PID_TYPE, "pid", Library.create(obj)
            )
            recs.append(rec)
        db.session.commit()
        return recs


class BorrowingRequestGenerator(Generator):
    """Borrowing requests generator."""

    def random_library_pid(self):
        """Get a random library PID if the state is ACCEPTED."""
        return random.choice(self.holder.pids("libraries", "pid"))

    def generate(self):
        """Generate."""
        size = self.holder.borrowing_requests["total"]
        objs = []
        for pid in range(1, size + 1):
            obj = {
                "pid": self.create_pid(),
                "status": random.choice(BorrowingRequest.STATUSES),
                "library_pid": self.random_library_pid(),
                "notes": lorem.sentence(),
            }
            if obj["status"] == "CANCELLED":
                obj["cancel_reason"] = lorem.sentence()
            objs.append(obj)

        self.holder.borrowing_requests["objs"] = objs

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.borrowing_requests["objs"]:
            rec = self._persist(
                BORROWING_REQUEST_PID_TYPE, "pid", BorrowingRequest.create(obj)
            )
            recs.append(rec)
        db.session.commit()
        return recs


class VendorGenerator(Generator):
    """Vendor generator."""

    def random_name(self):
        """Generate random name."""
        parts = lorem.sentence().split()
        return " ".join(parts[:min(randint(1, 2), len(parts))])

    def generate(self):
        """Generate."""
        size = self.holder.vendors["total"]
        objs = []
        for pid in range(1, size + 1):
            obj = {
                "pid": self.create_pid(),
                "name": self.random_name(),
                "address": "CERN\n1211 Geneva 23\nSwitzerland",
                "email": "visits.service@cern.ch",
                "phone": "+41 (0) 22 76 776 76",
                "notes": lorem.sentence(),
            }
            objs.append(obj)

        self.holder.vendors["objs"] = objs

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.vendors["objs"]:
            rec = self._persist(
                VENDOR_PID_TYPE, "pid", Vendor.create(obj)
            )
            recs.append(rec)
        db.session.commit()
        return recs


class OrderGenerator(Generator):
    """Order generator."""

    CURRENCIES = ["CHF", "EUR"]

    def random_date(self, start, end):
        """Generate random date between two dates."""
        delta = end - start
        int_delta = (delta.days * 24 * 3600) + delta.seconds
        return start + timedelta(seconds=random.randrange(int_delta))

    def random_price(self, currency=None, min_value=10.0):
        """Generate random price."""
        return {
            "currency": random.choice(self.CURRENCIES) if currency is None else currency,
            "value": round(min_value + random.random() * 100, 2),
        }

    def random_order_lines(self, status):
        """Generate random order lines."""
        doc_pids = self.holder.pids("documents", "pid")
        count = randint(1, 6)
        doc_pids = random.sample(doc_pids, count)
        for i in range(count):
            ordered = randint(1, 5)
            yield dict(
                copies_ordered=ordered,
                copies_received=randint(1, ordered) if status == 'RECEIVED' else 0,
                document_pid=doc_pids[i],
                is_donation=random.choice([True, False]),
                is_patron_suggestion=random.choice([True, False]),
                medium="PAPER",
                notes=lorem.sentence(),
                patron_pid=random.choice(self.holder.patrons_pids),
                payment_mode="CREDIT_CARD",
                purchase_type="PERPETUAL",
                recipient="PATRON",
                total_price=self.random_price(),
                unit_price=self.random_price(),
            )

    def generate(self):
        """Generate."""
        size = self.holder.orders["total"]
        objs = []
        now = datetime.now()
        for pid in range(1, size + 1):
            order_date = self.random_date(datetime(2010, 1, 1), now)
            status = random.choice(Order.STATUSES)
            order_lines = list(self.random_order_lines(status))
            grand_total = self.random_price(min_value=50.0)
            grand_total_main_currency = {
                "currency": "CHF",
                "value": grand_total["value"] * 1.10 if grand_total["currency"] == "EUR" else grand_total["value"],
            }
            obj = {
                "pid": self.create_pid(),
                "created_by_pid": self.holder.librarian_pid,
                "vendor_pid": random.choice(self.holder.vendors["objs"])["pid"],
                "status": status,
                "order_date": order_date.isoformat(),
                "notes": lorem.sentence(),
                "grand_total": grand_total,
                "grand_total_main_currency": grand_total_main_currency,
                "funds": list(set(lorem.sentence().split())),
                "payment": {
                    "mode": "CREDIT_CARD",
                },
                "order_lines": order_lines,
            }
            obj["expected_delivery_date"] = self.random_date(now, now + timedelta(days=400)).isoformat()
            if obj["status"] == "CANCELLED":
                obj["cancel_reason"] = lorem.sentence()
            elif obj["status"] == "RECEIVED":
                obj["received_date"] = self.random_date(order_date, now).isoformat()
            objs.append(obj)

        self.holder.orders["objs"] = objs

    def persist(self):
        """Persist."""
        recs = []
        for obj in self.holder.orders["objs"]:
            rec = self._persist(
                ORDER_PID_TYPE, "pid", Order.create(obj)
            )
            recs.append(rec)
        db.session.commit()
        return recs


@click.group()
def demo():
    """Demo data CLI."""


@demo.command()
@click.option("--docs", "n_docs", default=20)
@click.option("--items", "n_items", default=50)
@click.option("--eitems", "n_eitems", default=30)
@click.option("--loans", "n_loans", default=100)
@click.option("--internal-locations", "n_intlocs", default=10)
@click.option("--series", "n_series", default=10)
@click.option("--document-requests", "n_document_requests", default=10)
@click.option("--vendors", "n_vendors", default=10)
@click.option("--orders", "n_orders", default=30)
@click.option("--libraries", "n_libraries", default=10)
@click.option("--borrowing-requests", "n_borrowing_requests", default=10)
@with_appcontext
def data(
    n_docs,
    n_items,
    n_eitems,
    n_loans,
    n_intlocs,
    n_series,
    n_document_requests,
    n_vendors,
    n_orders,
    n_libraries,
    n_borrowing_requests
):
    """Insert demo data."""
    click.secho("Generating demo data", fg="yellow")

    indexer = RecordIndexer()

    vocabulary_dir = os.path.join(
        os.path.realpath("."), "invenio_app_ils", "vocabularies", "data")

    with open(os.path.join(vocabulary_dir, "tags.json")) as f:
        tags = json.loads(f.read())

    with open(os.path.join(vocabulary_dir, "languages.json")) as f:
        languages = json.loads(f.read())

    holder = Holder(
        patrons_pids=["1", "2", "5", "6"],
        languages=languages,
        librarian_pid="4",
        tags=tags,
        total_intloc=n_intlocs,
        total_items=n_items,
        total_eitems=n_eitems,
        total_documents=n_docs,
        total_loans=n_loans,
        total_series=n_series,
        total_document_requests=n_document_requests,
        total_vendors=n_vendors,
        total_orders=n_orders,
        total_borrowing_requests=n_borrowing_requests,
        total_libraries=n_libraries,
    )

    click.echo("Creating locations...")
    loc_generator = LocationGenerator(holder, minter)
    loc_generator.generate()
    rec = loc_generator.persist()
    indexer.index(rec)

    # InternalLocations
    intlocs_generator = InternalLocationGenerator(holder, minter)
    intlocs_generator.generate()
    rec_intlocs = intlocs_generator.persist()

    # Series
    click.echo("Creating series...")
    series_generator = SeriesGenerator(holder, minter)
    series_generator.generate()
    rec_series = series_generator.persist()

    # Documents
    click.echo("Creating documents...")
    documents_generator = DocumentGenerator(holder, minter)
    documents_generator.generate()
    rec_docs = documents_generator.persist()

    # Items
    click.echo("Creating items...")
    items_generator = ItemGenerator(holder, minter)
    items_generator.generate()
    rec_items = items_generator.persist()

    # EItems
    click.echo("Creating eitems...")
    eitems_generator = EItemGenerator(holder, minter)
    eitems_generator.generate()
    rec_eitems = eitems_generator.persist()

    # Loans
    click.echo("Creating loans...")
    loans_generator = LoanGenerator(holder, minter)
    loans_generator.generate()
    rec_loans = loans_generator.persist()

    # Related records
    click.echo("Creating related records...")
    related_generator = RecordRelationsGenerator(holder, minter)
    related_generator.generate(rec_docs, rec_series)
    related_generator.persist()

    # Document requests
    click.echo("Creating document requests...")
    document_requests_generator = DocumentRequestGenerator(holder, minter)
    document_requests_generator.generate()
    rec_requests = document_requests_generator.persist()

    # Vendors
    click.echo("Creating acquisition vendors...")
    vendor_generator = VendorGenerator(holder, minter)
    vendor_generator.generate()
    rec_vendors = vendor_generator.persist()

    # Orders
    click.echo("Creating acquisition orders...")
    order_generator = OrderGenerator(holder, minter)
    order_generator.generate()
    rec_orders = order_generator.persist()

    # Libraries
    click.echo("Creating ILL external libraries...")
    library_generator = LibraryGenerator(holder, minter)
    library_generator.generate()
    rec_libraries = library_generator.persist()

    # Borrowing requests
    click.echo("Creating ILL borrowing requests...")
    borrowing_requests_generator = BorrowingRequestGenerator(holder, minter)
    borrowing_requests_generator.generate()
    rec_borrowing_requests = borrowing_requests_generator.persist()

    # index locations
    indexer.bulk_index([str(r.id) for r in rec_intlocs])
    click.echo(
        "Sent to the indexing queue {0} locations".format(len(rec_intlocs))
    )

    # index series
    indexer.bulk_index([str(r.id) for r in rec_series])
    click.echo("Sent to the indexing queue {0} series".format(len(rec_series)))

    # index loans
    indexer.bulk_index([str(r.id) for r in rec_loans])
    click.echo("Sent to the indexing queue {0} loans".format(len(rec_loans)))

    click.secho("Now indexing...", fg="green")
    # process queue so items can resolve circulation status correctly
    indexer.process_bulk_queue()

    # index eitems
    indexer.bulk_index([str(r.id) for r in rec_eitems])
    click.echo("Sent to the indexing queue {0} eitems".format(len(rec_eitems)))

    # index items
    indexer.bulk_index([str(r.id) for r in rec_items])
    click.echo("Sent to the indexing queue {0} items".format(len(rec_items)))

    click.secho("Now indexing...", fg="green")
    # process queue so documents can resolve circulation correctly
    indexer.process_bulk_queue()

    # index libraries
    indexer.bulk_index([str(r.id) for r in rec_libraries])
    click.echo(
        "Sent to the indexing queue {0} libraries".format(
            len(rec_libraries)
        )
    )

    # index borrowing requests
    indexer.bulk_index([str(r.id) for r in rec_borrowing_requests])
    click.echo(
        "Sent to the indexing queue {0} borrowing requests".format(
            len(rec_borrowing_requests)
        )
    )

    click.secho("Now indexing...", fg="green")
    indexer.process_bulk_queue()

    # flush all indices after indexing, otherwise ES won't be ready for tests
    current_search.flush_and_refresh(index="*")

    # index documents
    indexer.bulk_index([str(r.id) for r in rec_docs])
    click.echo(
        "Sent to the indexing queue {0} documents".format(len(rec_docs))
    )

    # index document requests
    indexer.bulk_index([str(r.id) for r in rec_requests])
    click.echo(
        "Sent to the indexing queue {0} document requests".format(
            len(rec_requests)
        )
    )

    # index loans again
    indexer.bulk_index([str(r.id) for r in rec_loans])
    click.echo("Sent to the indexing queue {0} loans".format(len(rec_loans)))

    # index items again
    indexer.bulk_index([str(r.id) for r in rec_items])
    click.echo("Sent to the indexing queue {0} items".format(len(rec_items)))

    # index vendors
    indexer.bulk_index([str(r.id) for r in rec_vendors])
    click.echo(
        "Sent to the indexing queue {0} vendors".format(len(rec_vendors))
    )

    # index orders
    indexer.bulk_index([str(r.id) for r in rec_orders])
    click.echo(
        "Sent to the indexing queue {0} orders".format(len(rec_orders))
    )

    click.secho("Now indexing...", fg="green")
    indexer.process_bulk_queue()


@click.group()
def patrons():
    """Patrons data CLI."""


@patrons.command()
@with_appcontext
def index():
    """Index patrons."""
    from flask import current_app
    from invenio_app_ils.pidstore.pids import PATRON_PID_TYPE

    patrons = User.query.all()
    indexer = PatronIndexer()

    click.secho("Now indexing {0} patrons".format(len(patrons)), fg="green")

    rest_config = current_app.config["RECORDS_REST_ENDPOINTS"]
    patron_cls = rest_config[PATRON_PID_TYPE]["record_class"] or Patron
    for pat in patrons:
        patron = patron_cls(pat.id)
        indexer.index(patron)


def create_userprofile_for(email, username, full_name):
    """Create a fake user profile."""
    user = User.query.filter_by(email=email).one_or_none()
    if user:
        profile = UserProfile(user_id=int(user.get_id()))
        profile.username = username
        profile.full_name = full_name
        db.session.add(profile)
        db.session.commit()


@click.command()
@click.option("--recreate-db", is_flag=True, help="Recreating DB.")
@click.option(
    "--skip-demo-data", is_flag=True, help="Skip creating demo data."
)
@click.option(
    "--skip-file-location",
    is_flag=True,
    help="Skip creating file location."
)
@click.option("--skip-patrons", is_flag=True, help="Skip creating patrons.")
@click.option(
    "--skip-vocabularies",
    is_flag=True,
    help="Skip creating vocabularies."
)
@click.option("--verbose", is_flag=True, help="Verbose output.")
@with_appcontext
def setup(recreate_db, skip_demo_data, skip_file_location, skip_patrons,
          skip_vocabularies, verbose):
    """ILS setup command."""
    from flask import current_app
    from invenio_base.app import create_cli
    import redis

    click.secho("ils setup started...", fg="blue")

    # Clean redis
    redis.StrictRedis.from_url(
        current_app.config["CACHE_REDIS_URL"]
    ).flushall()
    click.secho("redis cache cleared...", fg="red")

    cli = create_cli()
    runner = current_app.test_cli_runner()

    def run_command(command, catch_exceptions=False):
        click.secho("ils {}...".format(command), fg="green")
        res = runner.invoke(cli, command, catch_exceptions=catch_exceptions)
        if verbose:
            click.secho(res.output)

    # Remove and create db and indexes
    if recreate_db:
        run_command("db destroy --yes-i-know", catch_exceptions=True)
        run_command("db init")
    else:
        run_command("db drop --yes-i-know")
    run_command("db create")
    run_command("index destroy --force --yes-i-know")
    run_command("index init --force")
    run_command("index queue init purge")

    # Create roles to restrict access
    run_command("roles create admin")
    run_command("roles create librarian")

    if not skip_patrons:
        # Create users
        run_command(
            "users create patron1@test.ch -a --password=123456"
        )  # ID 1
        create_userprofile_for("patron1@test.ch", "patron1", "Yannic Vilma")
        run_command(
            "users create patron2@test.ch -a --password=123456"
        )  # ID 2
        create_userprofile_for("patron2@test.ch", "patron2", "Diana Adi")
        run_command("users create admin@test.ch -a --password=123456")  # ID 3
        create_userprofile_for("admin@test.ch", "admin", "Zeki Ryoichi")
        run_command(
            "users create librarian@test.ch -a --password=123456"
        )  # ID 4
        create_userprofile_for("librarian@test.ch", "librarian", "Hector Nabu")
        run_command(
            "users create patron3@test.ch -a --password=123456"
        )  # ID 5
        create_userprofile_for("patron3@test.ch", "patron3", "Medrod Tara")
        run_command(
            "users create patron4@test.ch -a --password=123456"
        )  # ID 6
        create_userprofile_for("patron4@test.ch", "patron4", "Devi Cupid")

        # Assign roles
        run_command("roles add admin@test.ch admin")
        run_command("roles add librarian@test.ch librarian")

    if not skip_vocabularies:
        vocabularies_dir = os.path.join(
            os.path.realpath("."), "invenio_app_ils", "vocabularies", "data")
        json_files = " ".join(
            os.path.join(vocabularies_dir, name)
            for name in os.listdir(vocabularies_dir)
            if name.endswith(".json")
        )
        run_command("vocabulary index json --force {}".format(json_files))
        run_command("vocabulary index opendefinition spdx --force")
        run_command("vocabulary index opendefinition opendefinition --force")

    # Assign actions
    run_command("access allow superuser-access role admin")
    run_command("access allow ils-backoffice-access role librarian")

    # Index patrons
    run_command("patrons index")

    # Create files location
    if not skip_file_location:
        run_command("files location --default ils /tmp/ils-files")

    # Generate demo data
    if not skip_demo_data:
        run_command("demo data")

    click.secho("ils setup finished successfully", fg="blue")
