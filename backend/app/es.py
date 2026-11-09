"""The one Elasticsearch client the API and the loaders share."""

from elasticsearch import Elasticsearch

from .config import settings

es = Elasticsearch(settings.es_url, request_timeout=30)
