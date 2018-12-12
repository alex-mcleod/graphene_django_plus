from django.test import TestCase
from django.contrib.auth.models import Group, Permission, AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.test import RequestFactory

import base64

import graphene
from graphene.test import Client
from graphql.error import GraphQLError

from ..testing import GrapheneTestCase

from . import schema


class IntegrationTestCase(GrapheneTestCase):
    """ 
    Integration tests which use a test schema which is based on built-in Django
    models. 
    """

    def setUp(self):
        User = get_user_model()
        self.set_user(User.objects.create(first_name="Test", last_name="User"))
        self.set_schema(schema.test_schema)

    def test_can_list_based_on_permissions_and_filtering(self):
        """ Ensures that Permission handling works for queries. Users are 
        only supposed to be able to see groups they belong to. Also tests 
        whether filtering works. """
        g = Group.objects.create(name="test1")
        res = self.assertOK(
            """
            query {
                Group__List(first: 100, orderBy: ["id"]) {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
            """
        )
        self.assertEqual(len(res["data"]["Group__List"]["edges"]), 0)
        g.user_set.add(self.user)
        res = self.assertError(
            """
            query {
                Group__List(orderBy: ["id"]) {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
            """,
            "You must provide a `first` or `last` value to properly paginate",
        )
        res = self.assertOK(
            """
            query {
                Group__List(first: 100, orderBy: ["id"]) {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
            """
        )
        self.assertTrue(
            g.id in map(lambda g: g["node"]["id"], res["data"]["Group__List"]["edges"])
        )
        res = self.assertOK(
            """
            query {
                Group__List(first: 100, name_Icontains: "doesnotexist", orderBy: ["id"]) {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
            """
        )
        self.assertEqual(len(res["data"]["Group__List"]["edges"]), 0)
        res = self.assertOK(
            """
            query {
                Group__List(first: 100, name_Icontains: "%s", orderBy: ["id"]) {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
            """
            % (g.name)
        )
        self.assertEqual(len(res["data"]["Group__List"]["edges"]), 1)

    def test_can_get_single_entity_by_id(self):
        g = Group.objects.create(name="test2")
        # Permission settings should ensure this query fails.
        res = self.assertError(
            """
            query {
                Group__Item(id: %d) {
                    id
                    name
                }
            }
            """
            % g.id,
            "You do not have permission",
        )
        g.user_set.add(self.user)
        res = self.assertOK(
            """
            query {
                Group__Item(id: %d) {
                    id
                    name
                }
            }
            """
            % g.id
        )
        self.assertEqual(res["data"]["Group__Item"]["id"], g.id)

    def test_can_create_based_on_permissions(self):
        self.assertError(
            """
            mutation { 
                Group__Create(input: {name: "%s"}) {
                    ok
                }
            }
            """
            % schema.DISALLOW_CREATION,
            "You do not have permission",
        )
        res = self.assertOK(
            """
            mutation {
                Group__Create(input: {name: "my_new_group"}) {
                    ok
                }
            }
            """
        )
        self.assertTrue(res["data"]["Group__Create"]["ok"])
        self.assertTrue(Group.objects.get(name="my_new_group"))

    def test_optional_ordering_during_creation(self):
        self.assertError(
            """
            mutation { 
                Group__Create(input: {name: "someGroup"}) {
                    ok
                    edge {
                        cursor
                        node {
                            name
                        }
                    }
                }
            }
            """,
            "You cannot request the `edge` field without also specifying an ordering value using `edgeCursorOrderBy`",
        )
        # This mutation should work because edgeCursorOrderBy is set.
        res = self.assertOK(
            """
            mutation { 
                Group__Create(input: {name: "someGroup", edgeCursorOrderBy: ["id"]}) {
                    ok
                    edge {
                        cursor
                        node {
                            name
                        }
                    }
                }
            }
            """
        )
        self.assertTrue(res["data"]["Group__Create"]["edge"]["cursor"])
        self.assertEqual(
            res["data"]["Group__Create"]["edge"]["node"]["name"], "someGroup"
        )

    def test_can_update_based_on_permissions(self):
        g = Group.objects.create(name="test3")
        # User does not have permission to update group so this should return an error.
        self.assertError(
            """
            mutation { 
                Group__Update(input: {id: %d, name: "newName"}) {
                    ok
                    result {
                        id
                        name
                    }
                }
            }
            """
            % g.id,
            "You do not have permission",
        )
        g.user_set.add(self.user)
        res = self.assertOK(
            """
            mutation { 
                Group__Update(input: {id: %d, name: "newName"}) {
                    ok
                    result {
                        id
                        name
                    }
                }
            }
            """
            % g.id
        )
        g_data = res["data"]["Group__Update"]["result"]
        self.assertEqual(g_data["id"], g.id)
        g.refresh_from_db()
        self.assertEqual(g.name, "newName")

    def test_can_delete_based_on_permissions(self):
        g = Group.objects.create(name="test4")
        # User does not have permission to delete group so this should return an error.
        self.assertError(
            """
            mutation { 
                Group__Delete(input: {id: %d}) {
                    ok
                }
            }
            """
            % g.id,
            "You do not have permission",
        )
        self.assertTrue(Group.objects.filter(id=g.id).exists())
        g.user_set.add(self.user)
        res = self.assertOK(
            """
            mutation { 
                Group__Delete(input: {id: %d}) {
                    ok
                }
            }
            """
            % g.id
        )
        self.assertTrue(res["data"]["Group__Delete"]["ok"])
        self.assertFalse(Group.objects.filter(id=g.id).exists())

    def test_that_permissions_are_applied_when_accessing_via_related_entity(self):
        """ Permission classes should be applied even if a model is accessed 
        indirectly via a related model. """
        ctype = ContentType.objects.get(app_label="sites")
        perm_name = "MyPerm"
        perm = Permission.objects.create(
            content_type=ctype, name=perm_name, codename=perm_name
        )

        accessible_group = Group.objects.create(name="g1")
        accessible_group.permissions.add(perm)
        accessible_group.user_set.add(self.user)

        inaccessible_group = Group.objects.create(name="g2")
        inaccessible_group.permissions.add(perm)

        other_accessible_group = Group.objects.create(name="g3")
        other_accessible_group.user_set.add(self.user)

        res = self.assertOK(
            """
            query {
                Permission__Item(id: %s) {
                    name
                    codename
                    groupSet(first: 100, orderBy: ["-id", "-name"]) {
                        edges {
                            cursor
                            node {
                                id
                                name
                            }
                        }
                    }
                }
            }
            """
            % perm.id
        )
        group_ids = [
            edge["node"]["id"]
            for edge in res["data"]["Permission__Item"]["groupSet"]["edges"]
        ]

        self.assertTrue(accessible_group.id in group_ids)

        # We used `id` and `name` values for pagination, therefore the cursor for first the
        # element (which should be `accessble_group`) should include the `id` and `name`
        # of that element. This is not something Graphene does by default (array index is used
        # # instead), but our PermissionConnectionField makes sure cursors include
        # ordering attributes.
        first_cursor = res["data"]["Permission__Item"]["groupSet"]["edges"][0]["cursor"]
        first_cursor_decoded = base64.b64decode(first_cursor).decode("utf-8")
        self.assertEqual(
            first_cursor_decoded, f"{accessible_group.id}|{accessible_group.name}"
        )

        # Although user has permission for this, should not appear because
        # it is not attached to the permission we are fetching.
        self.assertFalse(other_accessible_group.id in group_ids)

        # Because the permission class only allows users to view
        # groups they are a part of, this should fail.
        self.assertFalse(inaccessible_group.id in group_ids)

        # This query should raise an exception because
        # ContentType permission class disallows access
        # to all content type objects.
        res = self.assertError(
            """
            query {
                Permission__Item(id: %s) {
                    name
                    codename
                    contentType {
                        appLabel
                    }
                }
            }
            """
            % perm.id,
            "You do not have permission",
        )
    
    def test_that_id_used_for_foreign_keys(self):
        ctype = ContentType.objects.get(app_label="sites")
        perm_name = "MyPerm"
        perm = Permission.objects.create(
            content_type=ctype, name=perm_name, codename=perm_name
        )
        res = self.assertOK(
            """
            mutation { 
                Permission__Update(input: {id: %d, name: "NewName", codename: "NewCodeName", contentType: %d}) {
                    ok
                    result {
                        id
                        name
                    }
                }
            }
            """
            % (perm.id, ctype.id)
        )

