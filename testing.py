from django.test import TestCase
from django.contrib.auth.models import Group, AnonymousUser
from django.contrib.auth import get_user_model
from django.test import RequestFactory

import logging

import graphene
from graphene.test import Client


class GrapheneTestCase(TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = AnonymousUser()
        self.schema = None

    def set_schema(self, schema):
        self.schema = schema

    def set_user(self, user):
        self.user = user

    def get_graphene_client(self):
        assert (
            self.schema is not None
        ), "Please call `set_schema` before calling `get_graphene_client`."
        c = Client(self.schema)
        c.user = self.user
        return c

    def execute(self, q_string):
        req = RequestFactory().get("/")
        req.user = self.user
        c = self.get_graphene_client()
        return c.execute(q_string, context_value=req)

    def assertOK(self, q_string):
        res = self.execute(q_string)
        assert not res.get(
            "errors"
        ), f"GraphQL operation unexpectedly failed with errors. Response was:\n\n{str(res)}"
        return res

    def assertError(self, q_string, err_string):
        # Disable logging because Graphene will log errors to the console
        # without actually throwing an exception. These tracebacks make test output
        # messy.
        logging.disable(level=logging.CRITICAL)
        res = self.execute(q_string)
        assert res.get(
            "errors"
        ), f"GraphQL operation unexpectedly succeeded. Response was:\n\n{str(res)}"
        assert err_string in str(
            res
        ), f'Error was raised, but expected error string "{err_string}" was not included. Response was:\n\n{str(res)}'
        logging.disable(level=logging.NOTSET)
        return res
