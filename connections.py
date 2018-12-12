from functools import partial

import graphene
from cursor_pagination import CursorPaginator
from django.db.models import QuerySet
from graphene.relay.connection import Iterable, PageInfo, connection_from_list
from graphene.types.utils import get_type
from graphene_django.filter import DjangoFilterConnectionField
from graphene_django.utils import maybe_queryset
from graphql_relay.utils import base64, is_str, unbase64
from graphql_relay.connection.arrayconnection import connection_from_list_slice


def OrderByField(required=True):
    return graphene.List(of_type=graphene.String, required=required)


class PermissionedConnectionField(DjangoFilterConnectionField):

    """ 
    Updated version of DjangoFilterConnectionField which utilizes `permission_class`
    to determine which items in queryset a given user can see. Also enforces use of 
    orderBy field to explicitly set order of results and uses cursor based pagination
    which is uses orderBy argument to determne unique cursors for items.
    """

    def __init__(self, node, permission_class, **kwargs):
        self.permission_class = permission_class
        super().__init__(
            node,
            # Add orderBy field here. It is then used in the connection_resolver below.
            # This field is required so that clients must be explicit about how they want data ordered.
            orderBy=OrderByField(),
            **kwargs
        )

    @classmethod
    def order_queryset(cls, qs, order_by_array):
        """ Override this to handle custom ordering arguments """
        return qs.order_by(*order_by_array)

    @classmethod
    def connection_resolver(
        cls,
        resolver,
        connection,
        default_manager,
        max_limit,
        enforce_first_or_last,
        filterset_class,
        filtering_args,
        permission_class,
        root,
        info,
        **args
    ):

        qs = default_manager.get_queryset()

        ordering = args["orderBy"]
        qs = cls.order_queryset(qs, ordering)

        permission = permission_class()
        permission.queryset = qs

        qs = permission.get_viewable(info.context.user)

        # Super method expects a manager, so just create one
        class Manager(object):
            def get_queryset(self):
                return qs

        return super(PermissionedConnectionField, cls).connection_resolver(
            resolver,
            connection,
            Manager(),
            max_limit,
            enforce_first_or_last,
            filterset_class,
            filtering_args,
            root,
            info,
            **args
        )

    def get_resolver(self, parent_resolver):
        return partial(
            self.connection_resolver,
            parent_resolver,
            self.type,
            self.get_manager(),
            self.max_limit,
            self.enforce_first_or_last,
            self.filterset_class,
            self.filtering_args,
            self.permission_class,
        )

    @classmethod
    def resolve_connection(cls, connection, default_manager, args, iterable):
        """ Have copied much of this from Graphene-Django package and updated to support ordering-aware cursor pagination. """
        if iterable is None:
            iterable = default_manager
        iterable = maybe_queryset(iterable)
        if isinstance(iterable, QuerySet):
            if iterable is not default_manager:
                default_queryset = maybe_queryset(default_manager)
                iterable = cls.merge_querysets(default_queryset, iterable)
            _len = iterable.count()
        else:
            _len = len(iterable)
        connection = connection_from_queryset(
            iterable,
            args,
            connection_type=connection,
            edge_type=connection.Edge,
            pageinfo_type=PageInfo,
        )
        connection.iterable = iterable
        connection.length = _len
        return connection


def get_paginator_for_queryset(qs, ordering):
    return CursorPaginator(qs, ordering=ordering)


def connection_from_queryset(qs, args, connection_type, edge_type, pageinfo_type):
    """ NOTE: Ordering used needs to uniquely determine position of each item in the 
    set. e.g. ordering by name alone may not (unless names are unique), but ordering with name and ID will. """
    ordering = args["orderBy"]
    paginator = get_paginator_for_queryset(qs, ordering)
    page = paginator.page(
        first=args.get("first"),
        last=args.get("last"),
        before=args.get("before"),
        after=args.get("after"),
    )
    edges = [edge_type(node=node, cursor=paginator.cursor(node)) for node in page.items]
    first_edge_cursor = edges[0].cursor if edges else None
    last_edge_cursor = edges[-1].cursor if edges else None
    return connection_type(
        edges=edges,
        page_info=pageinfo_type(
            start_cursor=first_edge_cursor,
            end_cursor=last_edge_cursor,
            has_previous_page=page.has_previous,
            has_next_page=page.has_next,
        ),
    )
