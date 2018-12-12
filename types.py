import graphene
from graphene.relay.node import (
    ID,
    Field,
    GlobalID,
    Interface,
    InterfaceOptions,
    OrderedDict,
)
from graphene_django import DjangoObjectType
from graphql.error import GraphQLError

from . import filters

from .node import PermissionedNode
from .connections import PermissionedConnectionField

from django.conf import settings
from myagi.settings import production_settings
from myagi.settings import development_settings
PROD_MEDIA_URL = production_settings.MEDIA_URL

from myagi_common.api.fields import image_file_exists


class PermissionedType(DjangoObjectType):

    """ Modified version of DjangoObjectType which ensures the `PermissionedNode`
    interface is added to the type. `PermissionedNode` makes it possible to a apply 
    a `permission_class` when accessing a given type instance. """

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, **options):
        options["interfaces"] = options.get("interfaces", tuple()) + (PermissionedNode,)
        permission_class = options.pop("permission_class", None)
        assert (
            permission_class
        ), f"You must specify a `permission_class` to use for the {cls.__name__} type."
        assert not options.get(
            "filter_fields"
        ), "Please use the `filterset_class` option instead of setting `filter_fields` directly."
        cls.permission_class = permission_class
        # Use `filterset_class` option or create one to prevent complaints from
        # django_filter. Default class will not allow filtering on any fields.
        cls.filterset_class = options.pop(
            "filterset_class", filters.deprecated_create_filter_class(options["model"])
        )
        return super().__init_subclass_with_meta__(**options)

    @classmethod
    def ensure_user_can_view_instance(cls, info, inst):
        permission_inst = cls.permission_class()
        permission_inst.queryset = cls._meta.model.objects.all()
        if not permission_inst.can_view(info.context.user, inst):
            raise GraphQLError(
                f"You do not have permission to view this {cls._meta.model.__name__} instance."
            )

    @classmethod
    def get_node(cls, info, id):
        try:
            inst = cls._meta.model.objects.get(pk=id)
        except cls._meta.model.DoesNotExist:
            raise GraphQLError(
                "Requested {cls._meta.model.__name__} instance does not exist."
            )
        cls.ensure_user_can_view_instance(info, inst)
        return inst


# File type that supports file based uploads and replaces url with either
# local url (if file exists locally) or prod media url
class DjangoFileType(graphene.Scalar):
    @staticmethod
    def serialize(value):
        try:
            url = value.url.replace(settings.MEDIA_URL, PROD_MEDIA_URL)
        except ValueError:
            return ""
        if settings.DEBUG and image_file_exists(value):
            url = value.url.replace(
                settings.MEDIA_URL,
                development_settings.LOCALHOST_MEDIA_URL
            )
        return url

    @staticmethod
    def parse_literal(node):
        if node.value:
            raise Exception('cannot set file type')

    @staticmethod
    def parse_value(value):
        if not value:
            return value
        raise Exception('cannot set file type')

