"""
Test knowledge graph generator.

Creates an in-memory RDFlib graph based on the trains ontology
with synthetic instance data for testing search and SPARQL functions.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

# Namespaces
TRAIN = Namespace("http://example.org/trains-ontology#")
EX = Namespace("http://example.org/instance/")

# Standard prefixes
PREFIXES: Dict[str, Namespace] = {
    "train": TRAIN,
    "ex": EX,
    "rdf": RDF,
    "rdfs": RDFS,
}

# ── synthetic test data ──────────────────────────────────────────────

# Countries
COUNTRIES: List[Dict[str, str]] = [
    {"id": "italy", "label": "Italy", "population": "59000000"},
    {"id": "france", "label": "France", "population": "67000000"},
    {"id": "switzerland", "label": "Switzerland", "population": "8700000"},
]

# Cities
CITIES: List[Dict[str, Optional[str]]] = [
    {"id": "milan", "label": "Milan", "country": "italy", "population": "1400000"},
    {"id": "rome", "label": "Rome", "country": "italy", "population": "2800000"},
    {"id": "paris", "label": "Paris", "country": "france", "population": "2100000"},
    {"id": "lyon", "label": "Lyon", "country": "france", "population": "520000"},
    {"id": "zurich", "label": "Zurich", "country": "switzerland", "population": "420000"},
]

# Stations
STATIONS: List[Dict[str, str]] = [
    {"id": "milano_centrale", "label": "Milano Centrale", "city": "milan"},
    {"id": "milano_porta_garibaldi", "label": "Milano Porta Garibaldi", "city": "milan"},
    {"id": "roma_termini", "label": "Roma Termini", "city": "rome"},
    {"id": "paris_gare_de_lyon", "label": "Paris Gare de Lyon", "city": "paris"},
    {"id": "lyon_part_dieu", "label": "Lyon Part-Dieu", "city": "lyon"},
    {"id": "zurich_hb", "label": "Zürich HB", "city": "zurich"},
]

# Train types
TRAIN_TYPES: List[Dict[str, str]] = [
    {"id": "frecciarossa", "label": "Frecciarossa"},
    {"id": "tgv", "label": "TGV"},
    {"id": "intercity", "label": "InterCity"},
]

# Trains with their details
TRAINS: List[Dict[str, str]] = [
    {
        "id": "fr_9528",
        "number": "FR 9528",
        "type": "frecciarossa",
        "departs": "milano_centrale",
        "arrives": "roma_termini",
        "dep_time": "07:00:00",
        "arr_time": "10:10:00",
        "duration": "190",
        "price": "89.90",
    },
    {
        "id": "fr_9530",
        "number": "FR 9530",
        "type": "frecciarossa",
        "departs": "milano_centrale",
        "arrives": "roma_termini",
        "dep_time": "08:30:00",
        "arr_time": "11:40:00",
        "duration": "190",
        "price": "99.90",
    },
    {
        "id": "tgv_9241",
        "number": "TGV 9241",
        "type": "tgv",
        "departs": "paris_gare_de_lyon",
        "arrives": "milano_porta_garibaldi",
        "dep_time": "06:45:00",
        "arr_time": "14:00:00",
        "duration": "435",
        "price": "120.00",
    },
    {
        "id": "ic_593",
        "number": "IC 593",
        "type": "intercity",
        "departs": "roma_termini",
        "arrives": "milano_centrale",
        "dep_time": "14:00:00",
        "arr_time": "17:30:00",
        "duration": "210",
        "price": "59.00",
    },
    {
        "id": "tgv_9255",
        "number": "TGV 9255",
        "type": "tgv",
        "departs": "lyon_part_dieu",
        "arrives": "paris_gare_de_lyon",
        "dep_time": "09:15:00",
        "arr_time": "11:05:00",
        "duration": "110",
        "price": "55.00",
    },
    {
        "id": "ic_601",
        "number": "IC 601",
        "type": "intercity",
        "departs": "zurich_hb",
        "arrives": "milano_centrale",
        "dep_time": "11:10:00",
        "arr_time": "14:40:00",
        "duration": "210",
        "price": "75.00",
    },
    {
        "id": "fr_9535",
        "number": "FR 9535",
        "type": "frecciarossa",
        "departs": "roma_termini",
        "arrives": "milano_centrale",
        "dep_time": "16:00:00",
        "arr_time": "19:10:00",
        "duration": "190",
        "price": "89.90",
    },
]


def _make_uri(suffix: str) -> URIRef:
    return EX[suffix]


def generate_trains_kg() -> Graph:
    """
    Build an in-memory RDFlib Graph with the trains ontology
    plus synthetic instance data.

    Returns
    -------
    rdflib.Graph
        Populated graph ready for testing.
    """
    g = Graph()

    # Bind prefixes for readability
    for prefix, ns in PREFIXES.items():
        g.bind(prefix, ns)

    # ── Ontology classes ─────────────────────────────────────────
    for cls_name in ["Train", "Station", "City", "Country", "TrainType"]:
        g.add((TRAIN[cls_name], RDF.type, RDFS.Class))
        g.add((TRAIN[cls_name], RDFS.label, Literal(cls_name, lang="en")))

    # ── Ontology properties ──────────────────────────────────────
    object_props = {
        "departsFrom": ("Train", "Station"),
        "arrivesAt": ("Train", "Station"),
        "hasType": ("Train", "TrainType"),
        "locatedIn": ("Station", "City"),
        "cityInCountry": ("City", "Country"),
        "passesThrough": ("Train", "Station"),
    }
    datatype_props = {
        "hasNumber": ("Train", "xsd:string"),
        "departureTime": ("Train", "xsd:time"),
        "arrivalTime": ("Train", "xsd:time"),
        "duration": ("Train", "xsd:integer"),
        "price": ("Train", "xsd:decimal"),
        "hasName": ("Station", "xsd:string"),
        "hasPopulation": ("City", "xsd:integer"),
    }

    for prop, (domain, range_) in object_props.items():
        g.add((TRAIN[prop], RDF.type, RDF.Property))
        g.add((TRAIN[prop], RDFS.domain, TRAIN[domain]))
        g.add((TRAIN[prop], RDFS.range, TRAIN[range_]))

    for prop, (domain, _range) in datatype_props.items():
        g.add((TRAIN[prop], RDF.type, RDF.Property))
        g.add((TRAIN[prop], RDFS.domain, TRAIN[domain]))

    # ── Instance data ────────────────────────────────────────────

    # Countries
    for c in COUNTRIES:
        uri = _make_uri(c["id"])
        g.add((uri, RDF.type, TRAIN.Country))
        g.add((uri, RDFS.label, Literal(c["label"], lang="en")))
        g.add((uri, TRAIN.hasPopulation, Literal(int(c["population"]))))

    # Cities
    for c in CITIES:
        uri = _make_uri(c["id"])
        g.add((uri, RDF.type, TRAIN.City))
        g.add((uri, RDFS.label, Literal(c["label"], lang="en")))
        g.add((uri, TRAIN.hasPopulation, Literal(int(c["population"]))))
        g.add((uri, TRAIN.cityInCountry, _make_uri(c["country"])))

    # Stations
    for s in STATIONS:
        uri = _make_uri(s["id"])
        g.add((uri, RDF.type, TRAIN.Station))
        g.add((uri, RDFS.label, Literal(s["label"], lang="en")))
        g.add((uri, TRAIN.hasName, Literal(s["label"])))
        g.add((uri, TRAIN.locatedIn, _make_uri(s["city"])))

    # Train types
    for t in TRAIN_TYPES:
        uri = _make_uri(t["id"])
        g.add((uri, RDF.type, TRAIN.TrainType))
        g.add((uri, RDFS.label, Literal(t["label"], lang="en")))

    # Trains
    for t in TRAINS:
        uri = _make_uri(t["id"])
        g.add((uri, RDF.type, TRAIN.Train))
        g.add((uri, TRAIN.hasNumber, Literal(t["number"])))
        g.add((uri, TRAIN.hasType, _make_uri(t["type"])))
        g.add((uri, TRAIN.departsFrom, _make_uri(t["departs"])))
        g.add((uri, TRAIN.arrivesAt, _make_uri(t["arrives"])))
        g.add((uri, TRAIN.departureTime, Literal(t["dep_time"])))
        g.add((uri, TRAIN.arrivalTime, Literal(t["arr_time"])))
        g.add((uri, TRAIN.duration, Literal(int(t["duration"]))))
        g.add((uri, TRAIN.price, Literal(float(t["price"]))))

    return g


# ── helper utilities for test assertions ──────────────────────────

def get_entity_label(g: Graph, entity_uri: str) -> Optional[str]:
    """Get rdfs:label for an entity, if present."""
    for _s, _p, o in g.triples((URIRef(entity_uri), RDFS.label, None)):
        return str(o)
    return None


def get_entity_type(g: Graph, entity_uri: str) -> Optional[str]:
    """Get the first rdf:type of an entity (excluding rdfs/owl built-ins)."""
    for _s, _p, o in g.triples((URIRef(entity_uri), RDF.type, None)):
        type_str = str(o)
        if "www.w3.org" not in type_str:
            return type_str
    return None