
from graphene_django.converter import convert_django_field

from graphene_django.filter.fields import DjangoConnectionField

from graphene_django.rest_framework.serializer_converter import get_graphene_type_from_serializer_field

from ..api.simple_api.fields import ExpandableRelatedField

from graphene import Dynamic, ID

from django.db import models

from rest_framework import serializers

from .fields import PermissionedTypeField

from .utils import create_permissioned_connection_field_for_type

""" 
These converters are all based on the defaults provided by graphene-django. 
Each has been changed to use permissioned versions of the default conversions
(i.e. PermissionedField and PermissionedConnectionField instead of Field and 
DjangoConnectionFilterField).
"""


@convert_django_field.register(models.ManyToManyField)
@convert_django_field.register(models.ManyToManyRel)
@convert_django_field.register(models.ManyToOneRel)
def convert_field_to_list_or_connection(field, registry=None):

    model = field.related_model

    def dynamic_type():
        _type = registry.get_type_for_model(model)
        if not _type:
            return
        assert hasattr(
            _type, "permission_class"
        ), "Attempt to connect to type which does not have a permission_class. Ensure it does by sub-classing `graphene_django_plus.types.PermissionedType`"
        return create_permissioned_connection_field_for_type(_type)
        # return DjangoConnectionField(_type)

    return Dynamic(dynamic_type)


@convert_django_field.register(models.OneToOneRel)
def convert_onetoone_field_to_djangomodel(field, registry=None):
    model = field.related_model

    def dynamic_type():
        _type = registry.get_type_for_model(model)
        if not _type:
            return
        return PermissionedTypeField(_type, required=not null)

    return Dynamic(dynamic_type)


@convert_django_field.register(models.OneToOneField)
@convert_django_field.register(models.ForeignKey)
def convert_field_to_djangomodel(field, registry=None):
    model = field.related_model

    def dynamic_type():
        _type = registry.get_type_for_model(model)
        if not _type:
            return
        return PermissionedTypeField(
            _type, description=field.help_text, required=not field.null
        )

    return Dynamic(dynamic_type)


@get_graphene_type_from_serializer_field.register(serializers.PrimaryKeyRelatedField)
@get_graphene_type_from_serializer_field.register(ExpandableRelatedField)
def convert_serializer_primary_key_related_field(field, is_input=True):
    return ID

